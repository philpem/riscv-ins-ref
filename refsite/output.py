"""Shared helpers for writing generated sites.

Both the ARM and RISC-V builders need the same output-path containment and
asset-copying behaviour, so it lives here rather than being duplicated.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROBOTS_TXT = "User-agent: *\nAllow: /\n"


def resolve_build_paths(
    output_dir: str | Path,
    assets_dir: str | Path,
    templates_dir: str | Path | None,
) -> tuple[Path, Path, Path]:
    """Resolve the output directory and default the template directory."""

    output = Path(output_dir).resolve()
    assets = Path(assets_dir)
    templates = Path(templates_dir) if templates_dir is not None else assets / "templates"
    return output, assets, templates


def write_relative(output_dir: str | Path, relative_path: str, content: str) -> Path:
    """Write *content* to *relative_path*, refusing to escape *output_dir*."""

    output = Path(output_dir).resolve()
    destination = (output / relative_path).resolve()
    if destination != output and output not in destination.parents:
        raise ValueError(f"output path escapes the build directory: {relative_path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def copy_files(source_dir: str | Path, target_dir: str | Path) -> int:
    """Copy the regular files directly inside *source_dir* into *target_dir*."""

    source = Path(source_dir)
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in sorted(source.iterdir()):
        if item.is_file():
            shutil.copy2(item, target / item.name)
            count += 1
    return count


def copy_shared_assets(assets_dir: str | Path, output_dir: str | Path) -> int:
    """Copy the CSS/fonts/Pagefind assets shared by every generated site."""

    assets = Path(assets_dir)
    output = Path(output_dir)
    count = 0
    count += copy_files(assets / "static", output / "static")
    count += copy_files(assets / "pagefind", output / "pagefind")
    (output / "robots.txt").write_text(ROBOTS_TXT, encoding="utf-8")
    return count
