#!/usr/bin/env python3
"""Generate the ARM reference website from Arm's reference tarballs.

Example:

    python3 generate.py --tarballs-dir .. --output build --pagefind

The generated tree is self-contained: ``index.html``, ``latest_aarch64/``,
``latest_sysreg/``, ``static/`` and ``pagefind/``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from refsite import archive
from refsite.archive import ArchiveError
from refsite.pagefind import PagefindError, run_pagefind
from refsite.site import SiteBuilder

HERE = Path(__file__).resolve().parent


class GenerationError(RuntimeError):
    """A user-facing error that should not produce a traceback."""


def _validate_output(output: Path, tarballs_dir: Path) -> None:
    """Reject output locations that would overwrite the generator or inputs."""

    if output.is_symlink():
        raise GenerationError(f"output path is a symbolic link: {output}")
    output = output.resolve()
    tarballs_dir = tarballs_dir.resolve()
    if output.exists() and not output.is_dir():
        raise GenerationError(f"output path is not a directory: {output}")
    if HERE.is_relative_to(output) or tarballs_dir.is_relative_to(output):
        raise GenerationError(
            "output directory must not contain the generator source or the tarball directory: "
            f"{output}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tarballs-dir",
        default=".",
        help="directory containing ISA_A64_xml_A_profile-*.tar.gz and SysReg_xml_A_profile-*.tar.gz (default: .)",
    )
    parser.add_argument(
        "--output",
        default="build",
        help="output directory for the generated site (default: build)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="version string used in the footer (default: derived from the tarball name)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="directory used to cache extracted tarballs (default: a temporary directory)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove the output directory before generating",
    )
    parser.add_argument(
        "--pagefind",
        action="store_true",
        help="run the Pagefind CLI after generating the site",
    )
    parser.add_argument(
        "--templates-dir",
        default=str(HERE / "templates"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--assets-dir",
        default=str(HERE),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output)
    tarballs_dir = Path(args.tarballs_dir)
    try:
        _validate_output(output, tarballs_dir)
    except GenerationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    output = output.resolve()

    if args.clean and output.exists():
        shutil.rmtree(output)

    try:
        extracted = archive.extract(tarballs_dir, args.work_dir)
    except ArchiveError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        version = args.version or extracted.version
        builder = SiteBuilder(
            a64_dir=extracted.a64_dir,
            sysreg_dir=extracted.sysreg_dir,
            output_dir=output,
            version=version,
            assets_dir=args.assets_dir,
            templates_dir=args.templates_dir,
        )
        stats = builder.build()
        print(f"Generated {stats.instructions} instruction pages")
        print(f"Generated {stats.registers} register pages")
        print(f"Generated {stats.listings} listing pages plus index.html")
        print(f"Copied {stats.assets} assets")
        print(f"Output: {output.resolve()}")

        if args.pagefind:
            try:
                run_pagefind(output)
            except PagefindError as error:
                print(f"warning: Pagefind index was not generated: {error}", file=sys.stderr)
                return 1
            print("Generated Pagefind index")
        return 0
    finally:
        archive.cleanup(extracted)


if __name__ == "__main__":
    raise SystemExit(main())
