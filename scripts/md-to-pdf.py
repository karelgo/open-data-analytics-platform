#!/usr/bin/env python3
"""Markdown → HTML → PDF zonder externe Python-deps.

Pipeline:
  1. Minimal markdown parser (stdlib-only) — voldoende voor onze docs:
     headings, code-fences/inline, fat/cursief, links, lists, tables,
     blockquotes, horizontal rules.
  2. Wrap in een geprinte HTML-template met GitHub-achtige CSS.
  3. Chrome headless → PDF (Chrome zit standaard op macOS-dev-machines).

Gebruik:
  python3 scripts/md-to-pdf.py docs/use-cases/uc11-customer-journey-walkthrough.md
  → docs/use-cases/uc11-customer-journey-walkthrough.pdf

Of expliciet:
  python3 scripts/md-to-pdf.py INPUT.md --output OUTPUT.pdf
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------- inline


_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _render_inline(text: str) -> str:
    """Markdown inline-syntax → HTML, in een veilige volgorde."""
    # Vervang eerst code-spans door placeholders zodat we niet per-ongeluk
    # markdown binnen `code` rendereren.
    placeholders: list[str] = []

    def _stash_code(match: re.Match) -> str:
        placeholders.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    text = _INLINE_CODE.sub(_stash_code, text)

    # Escape HTML in de rest.
    text = html.escape(text)

    # Re-render markdown inline (op de geëscape'de tekst).
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)

    def _link_repl(match: re.Match) -> str:
        label = match.group(1)
        url = match.group(2)
        # Niet-extern voorvoegsel werkt in PDF niet — laten staan met juiste escape.
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    text = _LINK.sub(_link_repl, text)

    # Plaats code-spans terug.
    def _unstash(match: re.Match) -> str:
        idx = int(match.group(1))
        return placeholders[idx]

    text = re.sub(r"\x00(\d+)\x00", _unstash, text)
    return text


# ---------------------------------------------------------------------- block


_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_CODE_FENCE = re.compile(r"^```(\w*)\s*$")
_HRULE = re.compile(r"^(?:[-*_]\s*){3,}$")
_UL_ITEM = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_OL_ITEM = re.compile(r"^(\s*)(\d+)\.\s+(.+)$")
_BLOCKQUOTE = re.compile(r"^>\s?(.*)$")
_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|\s*$")


def _parse_table(lines: list[str], i: int) -> tuple[str, int]:
    """Parse een GitHub-flavored table. Geeft (html, nieuwe-index) terug."""
    header_cells = [c.strip() for c in lines[i].strip("|").split("|")]
    # i+1 is de separator-rij (al gevalideerd door caller).
    j = i + 2
    body: list[list[str]] = []
    while j < len(lines) and _TABLE_ROW.match(lines[j]):
        body.append([c.strip() for c in lines[j].strip("|").split("|")])
        j += 1

    out: list[str] = ["<table>"]
    out.append("<thead><tr>")
    out.extend(f"<th>{_render_inline(c)}</th>" for c in header_cells)
    out.append("</tr></thead>")
    out.append("<tbody>")
    for row in body:
        out.append("<tr>")
        out.extend(f"<td>{_render_inline(c)}</td>" for c in row)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out), j


def _parse_list(lines: list[str], i: int, ordered: bool) -> tuple[str, int]:
    tag = "ol" if ordered else "ul"
    items: list[str] = []
    pattern = _OL_ITEM if ordered else _UL_ITEM
    while i < len(lines):
        m = pattern.match(lines[i])
        if not m:
            break
        text = m.group(3) if ordered else m.group(2)
        items.append(f"<li>{_render_inline(text)}</li>")
        i += 1
    return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>", i


def md_to_html(md: str) -> str:
    """Conversie. Niet 100% CommonMark-compliant — voldoende voor onze docs."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Blank line → paragraph-break (geen tag, blocks volgen).
        if not line.strip():
            i += 1
            continue

        # Code fence.
        m = _CODE_FENCE.match(line)
        if m:
            lang = m.group(1) or ""
            i += 1
            buf: list[str] = []
            while i < n and not _CODE_FENCE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            code_html = html.escape("\n".join(buf))
            lang_class = f' class="lang-{lang}"' if lang else ""
            out.append(f"<pre><code{lang_class}>{code_html}</code></pre>")
            continue

        # Heading.
        m = _HEADING.match(line)
        if m:
            level = len(m.group(1))
            text = _render_inline(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Horizontal rule.
        if _HRULE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # Table — header + separator pattern.
        if (
            _TABLE_ROW.match(line)
            and i + 1 < n
            and _TABLE_SEP.match(lines[i + 1])
        ):
            html_block, i = _parse_table(lines, i)
            out.append(html_block)
            continue

        # Lists.
        if _UL_ITEM.match(line):
            html_block, i = _parse_list(lines, i, ordered=False)
            out.append(html_block)
            continue
        if _OL_ITEM.match(line):
            html_block, i = _parse_list(lines, i, ordered=True)
            out.append(html_block)
            continue

        # Blockquote (kan multi-line zijn).
        if _BLOCKQUOTE.match(line):
            buf2: list[str] = []
            while i < n and _BLOCKQUOTE.match(lines[i]):
                buf2.append(_BLOCKQUOTE.match(lines[i]).group(1))
                i += 1
            quoted = " ".join(buf2).strip()
            out.append(f"<blockquote>{_render_inline(quoted)}</blockquote>")
            continue

        # Paragraph (verzamel tot lege regel of block-start).
        para: list[str] = [line]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            if (
                _HEADING.match(nxt)
                or _CODE_FENCE.match(nxt)
                or _HRULE.match(nxt)
                or _UL_ITEM.match(nxt)
                or _OL_ITEM.match(nxt)
                or _BLOCKQUOTE.match(nxt)
                or (
                    _TABLE_ROW.match(nxt)
                    and i + 1 < n
                    and _TABLE_SEP.match(lines[i + 1])
                )
            ):
                break
            para.append(nxt)
            i += 1
        out.append("<p>" + _render_inline(" ".join(para)) + "</p>")

    return "\n".join(out)


# ---------------------------------------------------------------------- shell


_CSS = """
@page { size: A4; margin: 18mm 16mm 22mm 16mm; }
html, body { background: #ffffff; }
body {
  font-family: -apple-system, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
  color: #1f2328;
  line-height: 1.55;
  font-size: 10.5pt;
  max-width: 100%;
  margin: 0;
}
h1, h2, h3, h4, h5, h6 {
  font-family: -apple-system, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
  font-weight: 600;
  line-height: 1.25;
  margin: 1.4em 0 0.5em;
  color: #1f2328;
  break-after: avoid;
}
h1 { font-size: 22pt; border-bottom: 1px solid #d0d7de; padding-bottom: .3em; margin-top: 0; }
h2 { font-size: 16pt; border-bottom: 1px solid #d8dee4; padding-bottom: .2em; }
h3 { font-size: 13pt; }
h4 { font-size: 11.5pt; color: #57606a; }
p { margin: 0.6em 0; }
ul, ol { margin: 0.4em 0 0.8em; padding-left: 1.6em; }
li { margin: 0.15em 0; }
li > p { margin: 0.2em 0; }
a { color: #0969da; text-decoration: none; word-break: break-all; }
a:hover { text-decoration: underline; }
code {
  font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  background: #eff1f3;
  border-radius: 4px;
  padding: 0.1em 0.35em;
  font-size: 9pt;
}
pre {
  background: #f6f8fa;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  padding: 0.75em 1em;
  overflow-x: auto;
  font-size: 9pt;
  line-height: 1.45;
  break-inside: avoid;
}
pre code { background: transparent; padding: 0; font-size: inherit; }
blockquote {
  margin: 0.8em 0;
  padding: 0.3em 0.9em;
  border-left: 3px solid #d0d7de;
  color: #57606a;
  background: #f6f8fa;
}
hr {
  border: 0;
  border-top: 1px solid #d0d7de;
  margin: 1.6em 0;
}
table {
  border-collapse: collapse;
  margin: 0.8em 0;
  width: 100%;
  font-size: 9.5pt;
  break-inside: avoid;
}
th, td {
  border: 1px solid #d0d7de;
  padding: 0.4em 0.7em;
  text-align: left;
  vertical-align: top;
}
th { background: #f6f8fa; font-weight: 600; }
tbody tr:nth-child(2n) { background: #fafbfc; }

.header-meta {
  font-size: 8.5pt;
  color: #6e7781;
  border-bottom: 1px solid #eaeef2;
  padding-bottom: 0.4em;
  margin-bottom: 1.2em;
}
"""


def render_html(md: str, title: str, source_path: Path) -> str:
    body = md_to_html(md)
    meta = (
        f"Bron: <code>{html.escape(str(source_path))}</code> · "
        f"Gegenereerd door <code>scripts/md-to-pdf.py</code>"
    )
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="header-meta">{meta}</div>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------------- chrome


def _find_chrome() -> str | None:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = _find_chrome()
    if not chrome:
        print(
            "FAIL: geen Chrome/Chromium/Edge gevonden. Installeer een Chromium-browser "
            "of pip-install `weasyprint` for a alternatief.",
            file=sys.stderr,
        )
        sys.exit(1)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path.absolute()}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not pdf_path.exists():
        print("Chrome stderr:\n" + result.stderr, file=sys.stderr)
        sys.exit(result.returncode or 1)


# ---------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown input file")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="PDF output (default: <input>.pdf)",
    )
    parser.add_argument(
        "--keep-html",
        action="store_true",
        help="Behoud het tussen-HTML-bestand naast de PDF.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"FAIL: {args.input} bestaat niet", file=sys.stderr)
        return 1

    md = args.input.read_text(encoding="utf-8")
    title = args.input.stem
    # Eerste # heading wordt de titel
    first_h1 = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if first_h1:
        title = first_h1.group(1).strip()

    html_str = render_html(md, title, args.input)

    html_path = args.input.with_suffix(".html") if args.keep_html \
                else Path("/tmp") / f"_md-to-pdf-{args.input.stem}.html"
    html_path.write_text(html_str, encoding="utf-8")

    pdf_path = args.output or args.input.with_suffix(".pdf")
    html_to_pdf(html_path, pdf_path)

    if not args.keep_html:
        html_path.unlink(missing_ok=True)

    size_kb = pdf_path.stat().st_size // 1024
    print(f"[md-to-pdf] {args.input} → {pdf_path} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
