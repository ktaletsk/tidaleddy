# Copied from Vortex (https://codeberg.org/uzu/vortex), commit aefea84ddde0b5f5e8e94c5a15d00504cb5e2439.
# Copyright (C) the Vortex authors ("Tidal Cyclists"). Licensed under GPL-3.0-or-later.
# Modified for tidaleddy, 2026-11-20: imports renamed from `vortex` to `eddy`; mini-notation fixed
# to match Tidal: `!n` makes n copies (was n + 1), copies are separate steps, each `?` has its own
# random seed, `{...}` without `%n` takes its steps from the first group (was 1), `0 .. 3` ranges,
# and lone `!` repeats. Changes are marked `tidaleddy:`.

import builtins
from fractions import Fraction

from parsimonious import NodeVisitor
from parsimonious.nodes import Node

from eddy.control import n, s
from eddy.pattern import pure  # polymeter,
from eddy.pattern import (
    choose_cycles,
    id,
    polyrhythm,
    rand,
    sequence,
    silence,
    stack,
    timecat,
)
from eddy.utils import flatten


class MiniVisitor(NodeVisitor):
    def visit_root(self, _node, children):
        _, sequence, _ = children
        return sequence

    def visit_sequence(self, _node, children):
        group, other_groups, other_seqs = children
        if isinstance(other_groups, Node):
            other_groups = []
        if isinstance(other_seqs, Node):
            other_seqs = []
        other_groups = [e[4] for e in other_groups]
        other_seqs = [e[3] for e in other_seqs]
        if other_groups:
            # Workaround: Re-build AST nodes as if it were a polyrhythm ("a b .
            # c" == "[a b] [c]")
            group = dict(
                type="sequence",
                elements=[
                    dict(
                        type="element",
                        value=dict(type="polyrhythm", seqs=[group]),
                        modifiers=[],
                    ),
                    *[
                        dict(
                            type="element",
                            value=dict(type="polyrhythm", seqs=[g]),
                            modifiers=[],
                        )
                        for g in other_groups
                    ],
                ],
            )
        if other_seqs:
            return dict(type="random_sequence", elements=[group, *other_seqs])
        return group

    def visit_group(self, _node, children):
        element, other_elements = children
        if isinstance(other_elements, Node):
            other_elements = []
        other_elements = [e[2] for e in other_elements]
        return dict(type="sequence", elements=[element] + other_elements)

    def visit_element(self, _node, children):
        value, euclid_modifier, modifiers, elongate, bare_repeats = children
        weight = 1 if isinstance(elongate, Node) else len(elongate) + 1
        # tidaleddy: each lone "!" after the element adds one more copy of it
        if not isinstance(bare_repeats, Node) and bare_repeats:
            repeat = next((m for m in modifiers if m["op"] == "repeat"), None)
            if repeat:
                repeat["count"] += len(bare_repeats)
            else:
                modifiers = [*modifiers, dict(type="modifier", op="repeat", count=len(bare_repeats))]
        element = dict(
            type="element",
            value=value,
        )
        if not isinstance(euclid_modifier, Node):
            element["euclid_modifier"] = euclid_modifier[0]
        weight_mod = next(
            (m for m in modifiers if m["op"] == "weight"),
            dict(type="modifier", op="weight", value=weight),
        )
        modifiers = [m for m in modifiers if m["op"] != "weight"]
        if weight_mod["value"] != 1:
            modifiers.append(weight_mod)
        element["modifiers"] = modifiers
        return element

    def visit_element_value(self, _node, children):
        return children[0]

    def visit_range(self, _node, children):
        # tidaleddy: "0 .. 3"
        start, _, _, _, end = children
        return dict(type="range", start=start, end=end)

    def visit_polyrhythm_subseq(self, _node, children):
        seqs = children[2]
        return dict(type="polyrhythm", seqs=seqs)

    def visit_polymeter_subseq(self, _node, children):
        seqs = children[2]
        steps = children[5]
        if isinstance(steps, Node):
            steps = None  # tidaleddy: the first sequence sets the steps (was 1)
        else:
            steps = steps[0]
        return dict(type="polymeter", seqs=seqs, steps=steps)

    def visit_polymeter_steps(self, _node, children):
        _, number = children
        return number

    def visit_polymeter1_subseq(self, _node, children):
        seqs = children[2]
        return dict(type="polymeter", seqs=seqs, steps=1)

    def visit_subseq_body(self, _node, children):
        # sequence (ws? ',' ws? sequence)*
        seq, other_seqs = children
        if isinstance(other_seqs, Node):
            other_seqs = []
        other_seqs = [s[3] for s in other_seqs]
        return [seq] + other_seqs

    ##
    # Terms
    #

    def visit_term(self, _node, children):
        # Workaround to return an AST element "number" for numbers
        if not isinstance(children[0], dict):
            return dict(type="number", value=children[0])
        return children[0]

    def visit_rest(self, _node, _children):
        return dict(type="rest")

    def visit_word_with_index(self, _node, children):
        word, index = children
        index = 0 if isinstance(index, Node) else index[0]
        return dict(type="word", value=word, index=index)

    def visit_index(self, _node, children):
        _, number = children
        return number

    ##
    # Modifiers
    #

    def visit_euclid_modifier(self, _node, children):
        _, _, k, _, _, _, n, rotation, _, _ = children
        mod = dict(type="euclid_modifier", k=k, n=n)
        if not isinstance(rotation, Node):
            mod["rotation"] = rotation[0]
        return mod

    def visit_euclid_rotation_param(self, _node, children):
        _, _, _, rotation = children
        return rotation

    def visit_modifiers(self, _node, children):
        mods = [m for m in children if m["op"] not in ("degrade", "weight")]

        # The degrade modifier (?) does not take into account application order,
        # so we merge them into a single modifier.
        # There are two kinds of degrade modifiers, depending on its argument:
        # 1) "count" (degrade1/degraden) and 2) "value" (degrader). If there is
        # at least one "value" argument, the last occurrence takes precedences
        # and overwrites other degrade modifiers.  Otherwise, we merge all other
        # "count" arguments into a single "count" modifier to simplify
        # representation.
        degrade_mods = [m for m in children if m["op"] == "degrade"]
        if degrade_mods:
            value_deg_mod = next(
                reversed([a for a in degrade_mods if a["value"]["op"] == "value"]), None
            )
            count_deg_mods = [a for a in degrade_mods if a["value"]["op"] == "count"]
            if value_deg_mod:
                mods.append(value_deg_mod)
            elif count_deg_mods:
                count_deg_mod = count_deg_mods[0].copy()
                deg_count = sum([m["value"]["value"] for m in count_deg_mods])
                count_deg_mod["value"]["value"] = deg_count
                mods.append(count_deg_mod)

        # The weight modifier (@) can be duplicated, but only the last one is
        # used, all others are ignored.
        weight_mods = [m for m in children if m["op"] == "weight"]
        if weight_mods:
            mods.append(weight_mods[-1])

        return mods

    def visit_modifier(self, _node, children):
        return children[0]

    def visit_fast(self, _node, children):
        _, value = children
        return dict(type="modifier", op="fast", value=_bare_element(value))

    def visit_slow(self, _node, children):
        _, value = children
        return dict(type="modifier", op="slow", value=_bare_element(value))

    def visit_repeat(self, _node, children):
        count = sum(flatten(children))
        return dict(type="modifier", op="repeat", count=count)

    def visit_repeatn(self, _node, children):
        _, _, count = children
        # tidaleddy: "bd!3" is three bd in total, so 2 more copies (was 3 more)
        return max(count - 1, 0)

    def visit_repeat1(self, _node, children):
        return 1

    def visit_degrade(self, _node, children):
        return dict(type="modifier", op="degrade", value=children[0])

    def visit_degrader(self, _node, children):
        _, _, value = children
        return dict(type="degrade_arg", op="value", value=value)

    def visit_degraden(self, _node, children):
        _, _, _, count = children
        return dict(type="degrade_arg", op="count", value=count)

    def visit_degrade1(self, _node, children):
        return dict(type="degrade_arg", op="count", value=1)

    def visit_weight(self, _node, children):
        _, number = children
        return dict(type="modifier", op="weight", value=number)

    ##
    # Primitives
    #

    def visit_word(self, node, _children):
        return node.text

    def visit_number(self, node, children):
        return children[0]

    def visit_real(self, node, _children):
        return float(node.text)

    def visit_integer(self, node, _children):
        return int(node.text)

    def visit_pos_integer(self, node, _children):
        return int(node.text)

    def visit_pos_real(self, node, _children):
        return float(node.text)

    ##
    # Others
    #

    def visit_ws(self, _node, _children):
        return

    def generic_visit(self, node, children):
        return children or node


def _bare_element(value):
    return dict(type="element", value=value, modifiers=[])


def _assign_degrade_seeds(node, seeds):
    """tidaleddy: number the `?` modifiers in the order they appear in the text.

    Like Tidal, each `?` uses its own random stream: seed k is `rand()` shifted
    earlier by k / 10000 of a cycle (Tidal: `rotL (0.0001 * seed) rand`).
    """
    if isinstance(node, dict):
        if node.get("type") == "modifier" and node.get("op") == "degrade" and builtins.id(node) not in seeds:
            # (builtins.id: this module imports Vortex's identity function as `id`)
            seeds[builtins.id(node)] = len(seeds)
        for value in node.values():
            _assign_degrade_seeds(value, seeds)
    elif isinstance(node, list):
        for item in node:
            _assign_degrade_seeds(item, seeds)


class MiniInterpreter:
    def __init__(self):
        self._seeds = {}

    def run(self, ast):
        """tidaleddy: evaluate a whole mini-notation AST, numbering its `?`s first."""
        self._seeds = {}
        _assign_degrade_seeds(ast, self._seeds)
        return self.eval(ast)

    def eval(self, node):
        node_type = node["type"]
        eval_method = getattr(self, f"eval_{node_type}")
        return eval_method(node)

    def eval_sequence(self, node):
        return self._eval_sequence_elements(node["elements"])

    def _eval_sequence_elements(self, elements):
        elements = [self.eval(n) for n in elements]
        tc_args = []
        # Because each element might have been replicated/repeated, each element
        # is actually a list of tuples (weight, pattern, degrade_ratio).
        for es in elements:
            # We extract the weight and degrade_ratio from the first element (it
            # does not matter from which element, all have the same state
            # values).
            weight = es[0][0] if es else 1
            deg = es[0][2] if es else 0
            # Use the length of the replicated element as weight times the
            # `weight` modifier (if present).  Build a sequence out of the
            # replicated elements and degrade by the accumulated degrade ratio.
            # tidaleddy: each copy is its own step, so "<a b>!" plays "a a" like
            # "<a b> <a b>" (fastcat made it "a b": alternations moved on per copy)
            pat = timecat(*[(1, e[1]) for e in es]) if len(es) > 1 else sequence(*[e[1] for e in es])
            if deg:
                # tidaleddy: each `?` has its own seed (see _assign_degrade_seeds)
                ratio, seed = deg
                pat = pat.degrade_by(ratio, rand().early(Fraction(seed, 10000)))
            tc_args.append((len(es) * weight, pat))
        # Finally use timecat to create a pattern out of this sequence
        return timecat(*tc_args)

    def eval_random_sequence(self, node):
        seqs = [self.eval(e) for e in node["elements"]]
        return choose_cycles(*seqs)

    def eval_polyrhythm(self, node):
        return polyrhythm(*[self.eval(seq) for seq in node["seqs"]])

    def eval_polymeter(self, node):
        # FIXME: Is there a better way to do this? It'd be nice to use
        # `polymeter()`, but the sequences are already "sequence" patterns, not
        # a list of events. We might need to restructure grammar...

        # return polymeter(*[self.eval(seq) for seq in node["seqs"]], steps=node["steps"])
        # tidaleddy: count steps the way the sequence lays them out (`a!2`, `a@3`
        # and `0 .. 3` are several steps), and with no %n use the first sequence's.
        counts = [self._steps(seq) for seq in node["seqs"]]
        steps = node["steps"] if node["steps"] is not None else counts[0]
        fast_params = [Fraction(steps) / count for count in counts]
        return stack(
            *[
                self.eval(seq).fast(fparam)
                for seq, fparam in zip(node["seqs"], fast_params)
            ]
        )

    def _steps(self, seq):
        """tidaleddy: how many steps a sequence has, counting repeats and weights."""
        if seq.get("type") != "sequence":
            return 1
        total = 0
        for element in seq["elements"]:
            es = self.eval(element)
            total += len(es) * (es[0][0] if es else 1)
        return total or 1

    def eval_range(self, node):
        start, end = node["start"], node["end"]
        step = 1 if end >= start else -1
        return [pure(i) for i in range(start, end + step, step)]

    def eval_element(self, node):
        # Here we collect all modifier functions of an element and reduce them
        modifiers = [self.eval(m) for m in node["modifiers"]]
        if node["value"]["type"] == "range":
            # tidaleddy: a range is several steps, like a repeated element
            values = [(1, p, 0) for p in self.eval(node["value"])]
            for modifier in modifiers:
                values = flatten([modifier(v) for v in values])
            return values
        pat = self.eval(node["value"])
        # Apply an euclid modifier if present
        if "euclid_modifier" in node:
            k, n, rotation = self.eval(node["euclid_modifier"])
            pat = pat.euclid(k, n, rotation)
        # The initial value is the tuple of 3 elements (see visit_modifier): a
        # default weight of 1, a "pure" pattern of the elements value and
        # degrade ratio of 0 (no degradation).  It is a list of tuples, because
        # modifiers return a list of tuples (there might be repeat modifiers
        # that return multiple patterns).
        values = [(1, pat, 0)]
        for modifier in modifiers:
            # We eventually flatten list of lists into a single list
            values = flatten([modifier(v) for v in values])
        return values

    def eval_euclid_modifier(self, node):
        k = self.eval(node["k"])
        n = self.eval(node["n"])
        rotation = self.eval(node["rotation"]) if "rotation" in node else pure(0)
        return k, n, rotation

    def eval_modifier(self, node):
        # This is a bit ugly, but we maintain the "state" of modifiers by returning
        # a tuple of 3 elements: (weight, pattern, degrade_ratio), where:
        #
        # * `weight` is the current weight value for timecat
        # * `pattern` is the modified pattern
        # * `degrade_ratio` is the accumulated degrade ratio.
        #
        # The return value of the modifier functions is a list of Patterns,
        # because the repeat modifier might return multiple patterns of the
        # element, so we generalize it into a list for all modifiers.
        if node["op"] == "degrade":
            # Use the formula `n / (n + 1)` to increase the degrade ratio
            # "linearly".  We expect there is a single degrade modifier
            # (guaranteed by the AST), so we can use the `count` as the final
            # count of degrade occurrences.
            arg = node["value"]
            seed = self._seeds.get(builtins.id(node), 0)  # tidaleddy: (ratio, seed)
            if arg["op"] == "count":
                return lambda w_p: [
                    (w_p[0], w_p[1], (Fraction(arg["value"], arg["value"] + 1), seed))
                ]
            elif arg["op"] == "value":
                return lambda w_p: [(w_p[0], w_p[1], (arg["value"], seed))]
        elif node["op"] == "repeat":
            return lambda w_p: [w_p] * (node["count"] + 1)
        elif node["op"] == "fast":
            param = self._eval_sequence_elements([node["value"]])
            return lambda w_p: [(w_p[0], w_p[1].fast(param), w_p[2])]
        elif node["op"] == "slow":
            param = self._eval_sequence_elements([node["value"]])
            return lambda w_p: [(w_p[0], w_p[1].slow(param), w_p[2])]
        elif node["op"] == "weight":
            # Overwrite current weight state value with the new weight from this
            # modifier.  The AST will only contain a single "weight" modifier,
            # so there is no issue with replacing it.
            return lambda w_p: [(node["value"], w_p[1], w_p[2])]
        return id

    def eval_number(self, node):
        return pure(node["value"])

    def eval_word(self, node):
        if node["index"]:
            return s(node["value"]) << n(node["index"])
        else:
            return pure(node["value"])

    def eval_rest(self, node):
        return silence()
