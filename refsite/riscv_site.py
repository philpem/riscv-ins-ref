"""Build orchestration for the RISC-V reference site.

This mirrors :mod:`refsite.site` but sources its content from the RISC-V
Unified Database's resolved specification instead of Arm's XML bundles.  The
document shell, chrome, search wiring and asset copying are shared.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .cheriot import apply_cheriot
from .model import BuildStats, Page
from .output import apply_base_url, copy_shared_assets, resolve_build_paths, write_relative
from .render import Renderer
from .riscv_render import (
    csr_listing,
    extension_listing,
    extension_members,
    instruction_listing,
    render_csr,
    render_extension,
    render_instruction,
)
from .riscv_spec import Spec, load_spec

SITE_TITLE = "RISC-V Reference"
SITE_DESCRIPTION = (
    "This site offers reference documentation for the RISC-V instruction set, "
    "control and status registers, and extensions, generated from the RISC-V "
    "Unified Database."
)
SITE_DESCRIPTION_PARAGRAPH = (
    "This site offers reference documentation for the RISC-V instruction set,\n"
    "      control and status registers, and extensions, generated from the\n"
    "      RISC-V Unified Database."
)
COPYRIGHT_TEXT = (
    "Data from the RISC-V Unified Database, copyright RISC-V International "
    "and contributors."
)
DISCLAIMER = (
    "This site is provided as a community resource and is NOT affiliated "
    "with nor endorsed by RISC-V International."
)
CHERIOT_CREDIT = (
    "CHERIoT extensions from the CHERIoT specification and Sail model, "
    "copyright Microsoft and the CHERIoT Platform contributors."
)

INSTRUCTION_LINKS = [
    {"href": "/latest_riscv/index.html", "label": "Instructions"},
]
REGISTER_LINKS = [
    {"href": "/latest_riscv/csrindex.html", "label": "CSRs"},
    {"href": "/latest_riscv/extindex.html", "label": "Extensions"},
]


class RiscvSiteBuilder:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Assemble the RISC-V site from a loaded specification."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        spec_dir: str | Path,
        output_dir: str | Path,
        version: str,
        assets_dir: str | Path,
        templates_dir: str | Path | None = None,
        overlay_dir: str | Path | None = None,
        cheriot_repo: str | Path | None = None,
        base_url: str = "",
    ) -> None:
        self.spec_dir = Path(spec_dir)
        self.output_dir, self.assets_dir, self.templates_dir = resolve_build_paths(
            output_dir, assets_dir, templates_dir
        )
        self.version = version
        self.overlay_dir = Path(overlay_dir) if overlay_dir is not None else None
        self.cheriot_repo = Path(cheriot_repo) if cheriot_repo is not None else None
        self.base_url = base_url
        self.renderer = Renderer(
            self.templates_dir,
            site_title=SITE_TITLE,
            copyright_text=COPYRIGHT_TEXT,
            disclaimer=DISCLAIMER,
            chrome_template="partials/riscv_chrome.html",
            cloudflare_template=None,
        )

    def build(self) -> BuildStats:
        """Render every page and copy the shared assets."""

        spec = load_spec(self.spec_dir, self.overlay_dir)
        if self.cheriot_repo is not None:
            apply_cheriot(spec, self.cheriot_repo)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        footer_html = self._footer_html()
        pages = self._content_pages(spec, footer_html)
        pages.extend(self._listing_pages(spec, footer_html))
        pages.append(self._home_page(footer_html))

        seen: set[str] = set()
        for page in pages:
            if not page.path:
                raise ValueError("page has no output path")
            if page.path in seen:
                raise ValueError(f"duplicate output path: {page.path}")
            seen.add(page.path)
            write_relative(self.output_dir, page.path, page.html)

        stats = BuildStats(
            instructions=len(spec.instructions),
            registers=len(spec.csrs),
            extensions=len(spec.extensions),
            listings=3,
        )
        stats.assets = self._copy_assets()
        apply_base_url(self.output_dir, self.base_url)
        return stats

    def _copy_assets(self) -> int:
        count = copy_shared_assets(self.assets_dir, self.output_dir)
        stylesheet = self.assets_dir / "riscv" / "riscv.css"
        if not stylesheet.is_file():
            raise FileNotFoundError(
                f"RISC-V stylesheet not found: {stylesheet} "
                "(the generated pages link to /static/riscv.css)"
            )
        shutil.copy2(stylesheet, self.output_dir / "static" / "riscv.css")
        return count + 1

    def _footer_html(self) -> str:
        credit = CHERIOT_CREDIT if self.cheriot_repo is not None else ""
        return self.renderer.riscv_footer_html(self.version, credit)

    def _content_pages(self, spec: Spec, footer_html: str) -> list[Page]:
        known_extensions = {extension.name for extension in spec.extensions}
        known_instructions = {instruction.name for instruction in spec.instructions}
        pages: list[Page] = []

        for instruction in spec.instructions:
            title, description, content_html = render_instruction(
                instruction,
                known_extensions=known_extensions,
                known_instructions=known_instructions,
            )
            page = self.renderer.riscv_instruction_page(
                title=title,
                description=description,
                content_html=content_html,
                version=self.version,
                footer_html=footer_html,
            )
            page.path = f"latest_riscv/insn/{instruction.name}.html"
            pages.append(page)

        for csr in spec.csrs:
            title, description, content_html = render_csr(csr)
            page = self.renderer.riscv_csr_page(
                title=title,
                description=description,
                content_html=content_html,
                version=self.version,
                footer_html=footer_html,
            )
            page.path = f"latest_riscv/csr/{csr.name}.html"
            pages.append(page)

        for extension in spec.extensions:
            instructions, csrs = extension_members(spec, extension)
            title, description, content_html = render_extension(
                extension, instructions=instructions, csrs=csrs
            )
            page = self.renderer.riscv_extension_page(
                title=title,
                description=description,
                content_html=content_html,
                version=self.version,
                footer_html=footer_html,
            )
            page.path = f"latest_riscv/ext/{extension.name}.html"
            pages.append(page)

        return pages

    def _listing_pages(self, spec: Spec, footer_html: str) -> list[Page]:
        listings = [
            ("All RISC-V Instructions", instruction_listing(spec), "latest_riscv/index.html"),
            ("All RISC-V CSRs", csr_listing(spec), "latest_riscv/csrindex.html"),
            ("All RISC-V Extensions", extension_listing(spec), "latest_riscv/extindex.html"),
        ]
        pages: list[Page] = []
        for title, listing_html, path in listings:
            page = self.renderer.listing_page(
                title=title,
                topbar_html="",
                listing_html=listing_html,
                head_template="head/riscv_listing.html",
                template="listing_riscv.html",
                footer_html=footer_html,
            )
            page.path = path
            pages.append(page)
        return pages

    def _home_page(self, footer_html: str) -> Page:
        return self.renderer.home_page(
            site_title=SITE_TITLE,
            site_description=SITE_DESCRIPTION,
            site_description_paragraph=SITE_DESCRIPTION_PARAGRAPH,
            instruction_links=INSTRUCTION_LINKS,
            register_links=REGISTER_LINKS,
            contact_url="",
            home_template="home_riscv.html",
            footer_html=footer_html,
        )
