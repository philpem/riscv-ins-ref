"""Build the alphabetic instruction and register listings.

Arm ships XSLT stylesheets for these indexes.  Running them gives the exact
list ordering, descriptions and whitespace that the published site used; we
only slice out the list itself and rewrite ``.xml`` links to ``.html``.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from .model import Page
from .render import Renderer

INSTRUCTION_TOPBAR = (
    '<table style="margin: 0 auto;">'
    '<tr><td><div class="topbar"><a href="index.html">Base</a></div></td>'
    '<td><div class="topbar"><a href="fpsimdindex.html">SIMD&amp;FP</a></div></td>'
    '<td><div class="topbar"><a href="sveindex.html">SVE</a></div></td>'
    '<td><div class="topbar"><a href="mortlachindex.html">SME</a></div></td>'
    "</tr></table>"
)

INSTRUCTION_INDEXES = [
    ("index.xml", "index.html"),
    ("fpsimdindex.xml", "fpsimdindex.html"),
    ("sveindex.xml", "sveindex.html"),
    ("mortlachindex.xml", "mortlachindex.html"),
]

REGISTER_INDEXES = [
    ("AArch64-regindex.xml", "AArch64-regindex.html", "AArch64 Registers"),
    ("AArch32-regindex.xml", "AArch32-regindex.html", "AArch32 Registers"),
]


def _parser() -> etree.XMLParser:
    return etree.XMLParser(load_dtd=False, no_network=True, recover=True, huge_tree=True)


def _run_xslt(xslt_path: Path, xml_path: Path) -> str:
    transform = etree.XSLT(etree.parse(str(xslt_path), _parser()))
    document = etree.parse(str(xml_path), _parser())
    return str(transform(document))


def _listing_region(document: str) -> str:
    heading_end = document.find("</h1>")
    if heading_end == -1:
        raise ValueError("XSLT output has no </h1>")
    start = document.find("\n", heading_end)
    if start == -1:
        raise ValueError("XSLT output has no newline after </h1>")
    start += 1
    end = document.find("<hr", start)
    if end == -1:
        end = document.find("<!-- Cloudflare", start)
    if end == -1:
        raise ValueError("XSLT output has no listing terminator")
    region = document[start:end]
    if not region.strip():
        raise ValueError("XSLT listing region is empty")
    return re.sub(r'(href=")(?!(?:https?:)?//)([^"]*?)\.xml(?=[#"])', r"\1\2.html", region)


def build_instruction_listings(a64_dir: str | Path, renderer: Renderer) -> list[Page]:
    a64_dir = Path(a64_dir)
    pages: list[Page] = []
    for xml_name, output_name in INSTRUCTION_INDEXES:
        region = _listing_region(_run_xslt(a64_dir / "alphaindex.xsl", a64_dir / xml_name))
        page = renderer.listing_page(
            title="All A64 Instructions",
            topbar_html=INSTRUCTION_TOPBAR,
            listing_html=region,
        )
        page.path = f"latest_aarch64/{output_name}"
        pages.append(page)
    return pages


def build_register_listings(sysreg_dir: str | Path, renderer: Renderer) -> list[Page]:
    sysreg_dir = Path(sysreg_dir)
    pages: list[Page] = []
    for xml_name, output_name, title in REGISTER_INDEXES:
        region = _listing_region(_run_xslt(sysreg_dir / "reg_alphaindex.xsl", sysreg_dir / xml_name))
        page = renderer.listing_page(
            title=title,
            topbar_html="",
            listing_html=region,
            extra_newlines=2,
        )
        page.path = f"latest_sysreg/{output_name}"
        pages.append(page)
    return pages
