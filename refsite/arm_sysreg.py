"""System-register adapter.

The SysReg bundle contains register pages, register-block pages and system
instruction pages.  The published site starts from the two register indexes and
publishes the transitive closure of local links.  That includes ordinary
registers, extension registers reachable from them, and only those system
instruction pages that a register page actually references.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from .html_transform import transform_sysreg
from .model import Page
from .render import Renderer

INDEX_PAGES = {
    "AArch64-regindex.html",
    "AArch32-regindex.html",
    "AArch64-sysindex.html",
    "AArch32-sysindex.html",
    "enc_index.html",
    "ext_alpha_index.html",
    "ext_enc_index.html",
    "func_index.html",
    "notice.html",
}

_LINK_RE = re.compile(r'(?:href|registerfile)="([^"#?]+)\.(?:xml|html)')


def _parser() -> etree.XMLParser:
    return etree.XMLParser(load_dtd=False, no_network=True, recover=True, huge_tree=True)


def _page_links(xhtml_path: Path) -> set[str]:
    text = xhtml_path.read_text(encoding="utf-8")
    return {Path(match.group(1)).name for match in _LINK_RE.finditer(text)}


def _index_seeds(sysreg_dir: Path) -> set[str]:
    seeds: set[str] = set()
    for name in ("AArch64-regindex.xml", "AArch32-regindex.xml"):
        path = sysreg_dir / name
        if not path.is_file():
            continue
        tree = etree.parse(str(path), _parser())
        for element in tree.iter():
            register_file = element.get("registerfile")
            if register_file:
                seeds.add(Path(register_file).name.removesuffix(".xml"))
    return seeds


def selected_register_files(sysreg_dir: str | Path) -> list[Path]:
    sysreg_dir = Path(sysreg_dir)
    xhtml_dir = sysreg_dir / "xhtml"
    all_pages = {path.stem: path for path in sorted(xhtml_dir.glob("*.html"))}
    index_stems = {Path(name).stem for name in INDEX_PAGES}

    seen: set[str] = set()
    seeds = _index_seeds(sysreg_dir)
    if not seeds:
        raise ValueError(
            f"no register index entries found in {sysreg_dir}; "
            "expected AArch64-regindex.xml or AArch32-regindex.xml"
        )
    pending = list(seeds)
    while pending:
        stem = pending.pop()
        if stem in seen or stem not in all_pages or stem in index_stems:
            continue
        seen.add(stem)
        pending.extend(_page_links(all_pages[stem]))

    return [all_pages[stem] for stem in sorted(seen)]


def build_register_pages(sysreg_dir: str | Path, renderer: Renderer, version: str) -> list[Page]:
    sysreg_dir = Path(sysreg_dir)
    pages: list[Page] = []
    for xhtml_path in selected_register_files(sysreg_dir):
        xml_path = sysreg_dir / f"{xhtml_path.stem}.xml"
        content_html, title, description = transform_sysreg(xhtml_path, xml_path)
        page = renderer.sysreg_page(
            title=title,
            description=description,
            content_html=content_html,
            version=version,
        )
        page.path = f"latest_sysreg/{xhtml_path.name}"
        pages.append(page)
    return pages
