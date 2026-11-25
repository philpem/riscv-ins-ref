"""Build orchestration for the ARM reference site."""

from __future__ import annotations

import shutil
from pathlib import Path

from .arm_isa import build_instruction_pages
from .arm_sysreg import build_register_pages
from .indexes import build_instruction_listings, build_register_listings
from .model import BuildStats, Page
from .output import copy_shared_assets, resolve_build_paths, write_relative
from .render import Renderer

SITE_TITLE = "Jon's Arm Reference"
SITE_DESCRIPTION = (
    "This site offers reference documentation for the AArch64 instruction set "
    "and system registers defined by the Armv8-A and Armv9-A architectures."
)
SITE_DESCRIPTION_PARAGRAPH = (
    "This site offers reference documentation for the AArch64 instruction set\n"
    "      and system registers defined by the Armv8-A and Armv9-A architectures."
)
CONTACT_URL = "https://jonpalmisc.com/contact"

INSTRUCTION_LINKS = [
    {"href": "/latest_aarch64/index.html", "label": "Base"},
    {"href": "/latest_aarch64/fpsimdindex.html", "label": "SIMD"},
    {"href": "/latest_aarch64/sveindex.html", "label": "SVE"},
    {"href": "/latest_aarch64/mortlachindex.html", "label": "SME"},
]
REGISTER_LINKS = [
    {"href": "/latest_sysreg/AArch64-regindex.html", "label": "AArch64"},
    {"href": "/latest_sysreg/AArch32-regindex.html", "label": "AArch32"},
]


class SiteBuilder:
    def __init__(
        self,
        *,
        a64_dir: str | Path,
        sysreg_dir: str | Path,
        output_dir: str | Path,
        version: str,
        assets_dir: str | Path,
        templates_dir: str | Path | None = None,
    ) -> None:
        self.a64_dir = Path(a64_dir)
        self.sysreg_dir = Path(sysreg_dir)
        self.output_dir, self.assets_dir, self.templates_dir = resolve_build_paths(
            output_dir, assets_dir, templates_dir
        )
        self.version = version
        self.renderer = Renderer(self.templates_dir, site_title=SITE_TITLE)

    def build(self) -> BuildStats:
        stats = BuildStats()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        pages: list[Page] = []
        instruction_pages = build_instruction_pages(self.a64_dir, self.renderer, self.version)
        register_pages = build_register_pages(self.sysreg_dir, self.renderer, self.version)
        listing_pages = build_instruction_listings(self.a64_dir, self.renderer) + build_register_listings(
            self.sysreg_dir, self.renderer
        )
        home = self.renderer.home_page(
            site_title=SITE_TITLE,
            site_description=SITE_DESCRIPTION,
            site_description_paragraph=SITE_DESCRIPTION_PARAGRAPH,
            instruction_links=INSTRUCTION_LINKS,
            register_links=REGISTER_LINKS,
            contact_url=CONTACT_URL,
        )
        pages.extend(instruction_pages)
        pages.extend(register_pages)
        pages.extend(listing_pages)
        pages.append(home)

        seen: set[str] = set()
        for page in pages:
            if not page.path:
                raise ValueError("page has no output path")
            if page.path in seen:
                raise ValueError(f"duplicate output path: {page.path}")
            seen.add(page.path)
            self._write(page.path, page.html)
        stats.instructions = len(instruction_pages)
        stats.registers = len(register_pages)
        stats.listings = len(listing_pages)
        stats.assets = self._copy_assets()
        return stats

    def _write(self, relative_path: str, content: str) -> None:
        write_relative(self.output_dir, relative_path, content)

    def _copy_assets(self) -> int:
        count = copy_shared_assets(self.assets_dir, self.output_dir)

        svg_dir = self.output_dir / "latest_aarch64"
        svg_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted((self.a64_dir / "xhtml").glob("*.svg")):
            shutil.copy2(source, svg_dir / source.name)
            count += 1

        (self.output_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        return count
