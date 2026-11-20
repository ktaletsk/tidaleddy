# Copied from Vortex (https://codeberg.org/uzu/vortex), commit aefea84ddde0b5f5e8e94c5a15d00504cb5e2439.
# Copyright (C) the Vortex authors ("Tidal Cyclists"). Licensed under GPL-3.0-or-later.
# Modified for tidaleddy, 2026-11-20: imports renamed from `vortex` to `eddy`; a fresh visitor and
# interpreter for every pattern (they now keep per-pattern state: the seeds of `?`).

import pprint

from eddy.mini.grammar import grammar
from eddy.mini.interpreter import MiniInterpreter, MiniVisitor


def parse_mini(code):
    raw_ast = grammar.parse(code)
    return MiniVisitor().visit(raw_ast)


def mini(code, print_ast=False):
    ast = parse_mini(code)
    if print_ast:
        pprint.pp(ast)
    return MiniInterpreter().run(ast)
