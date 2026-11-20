"""Build the eddy docs: Markdown pages with live marimo islands, run in the browser by Pyodide.

    .venv/bin/python docs/build.py                # writes docs/_site
    .venv/bin/python docs/build.py --local-wheel  # ...with eddy from this checkout
    python -m http.server -d docs/_site           # any static server works

Pages live in docs/pages/*.md. Besides ordinary Markdown, three kinds of
fenced block become marimo islands (cells that run in the reader's browser):

    ```eddy                     an editable, playable pattern (eddy.marimo.Repl).
    s("bd hh sn hh")            One line per layer. Options: cycles=4 cps=0.5
    ```

    ```python live              Python shown as code, followed by its live output
    play(s("bd*4"))             (sliders, players, tables...). Blocks share names
    ```                         like the cells of one marimo notebook.

    ```python hidden            runs, but shows nothing (setup code)
    ```

Each page is one marimo app. The cells run once here, at build time, so their
outputs are in the page before Python starts in the browser. Then Pyodide
installs the latest tidaleddy from PyPI and the islands come alive.

The build runs the examples with eddy from this checkout, but readers get the
release on PyPI. To preview docs that need unreleased changes, use --local-wheel:
it builds a wheel from this checkout and serves it with the site instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import markdown
from marimo import MarimoIslandGenerator
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

DOCS = Path(__file__).resolve().parent
REPO = DOCS.parent
PAGES = DOCS / "pages"
THEME = DOCS / "theme"
OUT = DOCS / "_site"

# With --local-wheel: Pyodide runs in a web worker, so wheel URLs must be absolute.
# Pages carry this placeholder, and a line of inline JS swaps in the site's address.
SITE_PLACEHOLDER = "@SITE@/"
FENCE = re.compile(r"^```(?P<lang>[\w-]+)(?P<opts>[^\n]*)\n(?P<body>.*?)^```[ \t]*$", re.M | re.S)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
ERROR_MIMETYPES = {"application/vnd.marimo+error"}


@dataclass
class Page:
    source: Path
    slug: str
    title: str
    nav: str
    order: int
    description: str
    body: str
    blocks: list[dict] = field(default_factory=list)

    @property
    def url(self) -> str:
        return "" if self.slug == "index" else f"{self.slug}/"

    @property
    def root(self) -> str:
        """Relative path from this page back to the site root."""
        return "./" if self.slug == "index" else "../"


def read_page(path: Path) -> Page:
    text = path.read_text()
    meta, body = {}, text
    if m := FRONTMATTER.match(text):
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    slug = path.stem
    title = meta.get("title", slug)
    return Page(path, slug, title, meta.get("nav", title), int(meta.get("order", 99)), meta.get("description", ""), body)


def options(opts: str) -> dict:
    out = {}
    for word in opts.split():
        if "=" in word:
            k, v = word.split("=", 1)
            out[k] = v
        else:
            out[word] = True
    return out


def code_html(code: str) -> str:
    return highlight(code, PythonLexer(), HtmlFormatter(cssclass="highlight", nowrap=False))


def extract_blocks(page: Page) -> str:
    """Swap island blocks for placeholders, remembering what each one is."""

    def swap(m: re.Match) -> str:
        lang, opts, body = m.group("lang"), options(m.group("opts")), m.group("body").rstrip("\n")
        if lang == "eddy":
            lines = [line for line in body.splitlines() if line.strip()]
            args = ", ".join(json.dumps(line) for line in lines)
            kw = "".join(f", {k}={float(v) if k == 'cps' else int(v)}" for k, v in opts.items() if k in ("cycles", "cps"))
            code = f"from eddy.marimo import Repl as _Repl\n_Repl({args}{kw})"
            block = {"kind": "eddy", "code": code, "shown": body}
        elif lang == "python" and ("live" in opts or "hidden" in opts):
            block = {"kind": "live" if "live" in opts else "hidden", "code": body, "shown": body}
        else:
            return m.group(0)
        page.blocks.append(block)
        return f'\n<div class="eddy-slot" data-slot="{len(page.blocks) - 1}"></div>\n'

    return FENCE.sub(swap, page.body)


async def build_islands(page: Page, dependency: str) -> tuple[list[str], MarimoIslandGenerator]:
    """Run the page's cells and return the HTML for each block."""
    gen = MarimoIslandGenerator(app_id=page.slug)
    stubs = [gen.add_code(b["code"], display_code=False, display_output=b["kind"] != "hidden") for b in page.blocks]
    gen._dependencies = [dependency]  # what Pyodide installs before running the cells
    await gen.build()
    for block, stub in zip(page.blocks, stubs):
        out = stub.output
        if out is not None and out.mimetype in ERROR_MIMETYPES:
            raise SystemExit(f"{page.source.name}: a block failed to run at build time:\n{block['code']}\n{out.data}")
    rendered = []
    for block, stub in zip(page.blocks, stubs):
        island = stub.render()
        if block["kind"] == "eddy":
            rendered.append(
                '<div class="eddy-block eddy-repl-block">'
                f'<div class="eddy-fallback" aria-hidden="true">{code_html(block["shown"])}'
                '<div class="eddy-fallback-note">▶ starting Python…</div></div>'
                f"{island}</div>"
            )
        elif block["kind"] == "live":
            quiet = not re.sub(r"<[^>]*>|\s", "", stub._output_html())  # e.g. a cell of imports
            rendered.append(
                f'<div class="eddy-block eddy-live-block{" is-quiet" if quiet else ""}">'
                f'<div class="eddy-live-code">{code_html(block["shown"])}</div>'
                f'<div class="eddy-live-output">{island}</div></div>'
            )
        else:
            rendered.append(f'<div class="eddy-hidden-block">{island}</div>')
    return rendered, gen


def render_markdown(text: str):
    md = markdown.Markdown(
        extensions=["tables", "toc", "admonition", "attr_list", "md_in_html", "pymdownx.superfences", "pymdownx.highlight"],
        extension_configs={
            "toc": {"permalink": "#", "toc_depth": "2-3"},
            "pymdownx.highlight": {"css_class": "highlight", "use_pygments": True},
        },
    )
    out = md.convert(text)
    return out, md.toc_tokens


def toc_html(tokens) -> str:
    items = []
    for t in tokens:
        if t["level"] == 1:
            items.extend(t.get("children", []))
        else:
            items.append(t)
    if not items:
        return ""
    lis = []
    for t in items:
        sub = "".join(f'<li><a href="#{c["id"]}">{c["name"]}</a></li>' for c in t.get("children", []))
        lis.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>{f"<ul>{sub}</ul>" if sub else ""}</li>')
    return "<p class=\"toc-title\">On this page</p><ul>" + "".join(lis) + "</ul>"


def nav_html(pages: list[Page], current: Page) -> str:
    items = []
    for p in pages:
        cls = ' class="active" aria-current="page"' if p is current else ""
        items.append(f'<li><a href="{current.root}{p.url}"{cls}>{html.escape(p.nav)}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def pager_html(pages: list[Page], current: Page) -> str:
    i = pages.index(current)
    prev = pages[i - 1] if i > 0 else None
    nxt = pages[i + 1] if i + 1 < len(pages) else None
    parts = []
    if prev:
        parts.append(f'<a class="pager-prev" href="{current.root}{prev.url}"><span>Previous</span>{html.escape(prev.nav)}</a>')
    else:
        parts.append("<span></span>")
    if nxt:
        parts.append(f'<a class="pager-next" href="{current.root}{nxt.url}"><span>Next</span>{html.escape(nxt.nav)}</a>')
    return "".join(parts)


def repo_url() -> str:
    """The source repository: EDDY_REPO_URL, or the repo GitHub Actions is building, or none."""
    if url := os.environ.get("EDDY_REPO_URL"):
        return url.rstrip("/")
    if repo := os.environ.get("GITHUB_REPOSITORY"):
        return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}"
    return ""


def repo_links(page: Page) -> tuple[str, str]:
    """The header's repository link and the page's "Edit this page" link (empty without a repo)."""
    url = repo_url()
    if not url:
        return "", ""
    branch = os.environ.get("EDDY_REPO_BRANCH") or os.environ.get("GITHUB_REF_NAME") or "main"
    source = page.source.relative_to(REPO).as_posix()
    header = (
        f'<a class="icon-button repo-link" href="{html.escape(url)}" aria-label="Source code">'
        '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.36 1.09 2.93.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.69-4.57 4.94.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"/></svg></a>'
    )
    edit = f'<p class="edit-link"><a href="{html.escape(url)}/edit/{html.escape(branch)}/{source}">Edit this page</a></p>'
    return header, edit


def build_wheel() -> Path:
    """Build tidaleddy's wheel and put it in the site, in a folder named after its contents."""
    tmp = OUT / "_wheel"
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp), str(REPO)], check=True, capture_output=True)
    wheel = next(tmp.glob("tidaleddy-*.whl"))
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()[:12]
    dest = OUT / "wheels" / digest / wheel.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(wheel), dest)
    shutil.rmtree(tmp)
    return dest.relative_to(OUT)


def pygments_css() -> str:
    light = HtmlFormatter(style="friendly").get_style_defs(".highlight")
    dark = HtmlFormatter(style="github-dark").get_style_defs(":root.dark .highlight")
    # keep the themes' token colours, but let the page set code backgrounds
    strip_bg = lambda css: re.sub(r"\.highlight \{ background: [^;]+; \}", "", css)
    return strip_bg(light) + "\n" + re.sub(r":root\.dark \.highlight \{ background: [^;]+; \}", "", dark)


async def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if "--local-wheel" in sys.argv[1:]:
        wheel = build_wheel()
        dependency = f"tidaleddy[marimo] @ {SITE_PLACEHOLDER}{wheel.as_posix()}"
        source = wheel.as_posix()
    else:
        dependency = "tidaleddy[marimo]"  # the latest release on PyPI
        source = "tidaleddy from PyPI"

    pages = sorted((read_page(p) for p in PAGES.glob("*.md")), key=lambda p: (p.order, p.slug))
    template = (THEME / "page.html").read_text()
    for asset in ("style.css", "site.js", "logo.svg"):
        shutil.copy(THEME / asset, OUT / asset)
    (OUT / "pygments.css").write_text(pygments_css())

    for page in pages:
        text = extract_blocks(page)
        body, tokens = render_markdown(text)
        head = ""
        payload = ""
        if page.blocks:
            blocks, gen = await build_islands(page, dependency)
            for i, b in enumerate(blocks):
                body = body.replace(f'<div class="eddy-slot" data-slot="{i}"></div>', b)
            head = gen.render_head()
            payload = gen.render_payload_script()
        header_link, edit_link = repo_links(page)
        out = (
            template.replace(
                "{{page_title}}",
                "eddy · TidalCycles patterns in Python" if page.slug == "index" else f"{html.escape(page.title)} · eddy",
            )
            .replace("{{title}}", html.escape(page.title))
            .replace("{{description}}", html.escape(page.description))
            .replace("{{root}}", page.root)
            .replace("{{islands_head}}", head)
            .replace("{{nav}}", nav_html(pages, page))
            .replace("{{toc}}", toc_html(tokens))
            .replace("{{content}}", body)
            .replace("{{pager}}", pager_html(pages, page))
            .replace("{{payload}}", payload)
            .replace("{{has_islands}}", "true" if page.blocks else "false")
            .replace("{{repo_link}}", header_link)
            .replace("{{edit_link}}", edit_link)
        )
        dest = OUT / page.url / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out)
        print(f"  {page.slug:16} {len(page.blocks):2} islands  {len(out) // 1024:4} KB")
    print(f"built {len(pages)} pages into {OUT.relative_to(REPO)}/; readers get {source}")


if __name__ == "__main__":  # the islands build runs cells in a subprocess that re-imports this file
    sys.exit(asyncio.run(main()))
