#!/usr/bin/env python3
"""Generate the ARM or RISC-V reference website.

Examples:

    python3 generate.py --tarballs-dir .. --output build --pagefind
    python3 generate.py --arch riscv --tarballs-dir .. --output build-riscv
    python3 generate.py --arch riscv --udb-repo ../riscv-unified-db --output build-riscv
    python3 generate.py --arch riscv --udb-repo ../riscv-unified-db \\
        --cheriot-repo ../cheriot-sail --output build-riscv

The generated ARM tree is self-contained: ``index.html``, ``latest_aarch64/``,
``latest_sysreg/``, ``static/`` and ``pagefind/``.  The RISC-V tree contains
``latest_riscv/`` instead.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from refsite import archive, riscv_archive
from refsite.archive import ArchiveError
from refsite.cheriot import CheriotError
from refsite.model import BuildStats
from refsite.pagefind import PagefindError, run_pagefind
from refsite.riscv_archive import RiscvArchiveError
from refsite.riscv_site import RiscvSiteBuilder
from refsite.riscv_spec import SpecError, find_spec_root
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
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arch",
        choices=("arm", "riscv"),
        default="arm",
        help="architecture to generate (default: arm)",
    )
    parser.add_argument(
        "--tarballs-dir",
        default=".",
        help=(
            "directory containing the source bundles: ISA_A64_xml_A_profile-*.tar.gz "
            "and SysReg_xml_A_profile-*.tar.gz for ARM, or resolved_spec*.tar.gz for "
            "RISC-V (default: .)"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "output directory for the generated site "
            "(default: build for ARM, build-riscv for RISC-V)"
        ),
    )
    parser.add_argument(
        "--version",
        default=None,
        help="version string used in the footer (default: derived from the tarball name)",
    )
    parser.add_argument(
        "--overlay-dir",
        default=None,
        help=(
            "RISC-V only: directory of inst/, csr/ and ext/ YAML files that "
            "replace or extend the base specification (default: none)"
        ),
    )
    parser.add_argument(
        "--spec-dir",
        default=None,
        help=(
            "RISC-V only: use an already-resolved specification directory "
            "instead of extracting a tarball"
        ),
    )
    parser.add_argument(
        "--udb-repo",
        default=None,
        help=(
            "RISC-V only: path to a riscv-unified-db git checkout containing "
            "gen/resolved_spec; the short commit hash is used as the version"
        ),
    )
    parser.add_argument(
        "--cheriot-repo",
        default=None,
        help=(
            "RISC-V only: path to a cheriot-sail checkout (or its "
            "src/cheri_insts.sail) whose capability instructions are added "
            "to the site"
        ),
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


def _build_arm(args: argparse.Namespace, output: Path, tarballs_dir: Path) -> BuildStats:
    """Extract the ARM bundles and build the ARM site."""

    extracted = archive.extract(tarballs_dir, args.work_dir)
    try:
        builder = SiteBuilder(
            a64_dir=extracted.a64_dir,
            sysreg_dir=extracted.sysreg_dir,
            output_dir=output,
            version=args.version or extracted.version,
            assets_dir=args.assets_dir,
            templates_dir=args.templates_dir,
        )
        return builder.build()
    finally:
        archive.cleanup(extracted)


def _git_short_revision(repo: Path) -> str:
    """Return git's shortest unambiguous revision for *repo*."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise GenerationError(f"could not run git: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or "not a git checkout"
        raise GenerationError(f"could not read the revision of {repo}: {detail}")
    return result.stdout.strip()


def _resolve_udb_repo(repo: Path) -> tuple[Path, str]:
    """Find the resolved specification and revision in a UDB checkout."""

    if not repo.is_dir():
        raise GenerationError(f"UDB checkout not found: {repo}")
    version = _git_short_revision(repo)
    try:
        spec_dir = find_spec_root(repo / "gen" / "resolved_spec")
    except SpecError as error:
        raise GenerationError(
            f"no resolved specification in {repo}/gen/resolved_spec; "
            "run './do gen:resolved_arch' in the checkout first"
        ) from error
    return spec_dir, version


def _cheriot_version(version: str, repo: str | Path | None) -> str:
    """Append the CHERIoT checkout's short revision to *version*."""

    if not repo:
        return version
    path = Path(repo)
    if not path.is_dir():
        return version
    try:
        revision = _git_short_revision(path)
    except GenerationError:
        return version
    return f"{version}+cheriot.{revision}"


def _build_riscv(args: argparse.Namespace, output: Path, tarballs_dir: Path) -> BuildStats:
    """Build the RISC-V site from a UDB checkout, a spec directory or a tarball."""

    if args.spec_dir:
        spec_dir = Path(args.spec_dir)
        version = args.version or _cheriot_version(
            _git_short_revision(Path(args.udb_repo)) if args.udb_repo else "unknown",
            args.cheriot_repo,
        )
        builder = RiscvSiteBuilder(
            spec_dir=spec_dir,
            output_dir=output,
            version=version,
            assets_dir=args.assets_dir,
            templates_dir=args.templates_dir,
            overlay_dir=args.overlay_dir,
            cheriot_repo=args.cheriot_repo,
        )
        return builder.build()

    if args.udb_repo:
        spec_dir, version = _resolve_udb_repo(Path(args.udb_repo))
        builder = RiscvSiteBuilder(
            spec_dir=spec_dir,
            output_dir=output,
            version=args.version or _cheriot_version(version, args.cheriot_repo),
            assets_dir=args.assets_dir,
            templates_dir=args.templates_dir,
            overlay_dir=args.overlay_dir,
            cheriot_repo=args.cheriot_repo,
        )
        return builder.build()

    extracted = riscv_archive.extract(tarballs_dir, args.work_dir)
    try:
        builder = RiscvSiteBuilder(
            spec_dir=extracted.spec_dir,
            output_dir=output,
            version=args.version
            or _cheriot_version(extracted.version, args.cheriot_repo),
            assets_dir=args.assets_dir,
            templates_dir=args.templates_dir,
            overlay_dir=args.overlay_dir,
            cheriot_repo=args.cheriot_repo,
        )
        return builder.build()
    finally:
        riscv_archive.cleanup(extracted)


def main(  # pylint: disable=too-many-return-statements,too-many-branches
    argv: list[str] | None = None,
) -> int:
    """Run the generator and return a process exit code."""

    args = parse_args(argv)
    if args.overlay_dir and args.arch != "riscv":
        print("error: --overlay-dir requires --arch riscv", file=sys.stderr)
        return 2
    if (args.spec_dir or args.udb_repo) and args.arch != "riscv":
        print("error: --spec-dir and --udb-repo require --arch riscv", file=sys.stderr)
        return 2
    if args.cheriot_repo and args.arch != "riscv":
        print("error: --cheriot-repo requires --arch riscv", file=sys.stderr)
        return 2
    if args.output:
        output = Path(args.output)
    else:
        output = Path("build-riscv" if args.arch == "riscv" else "build")
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
        if args.arch == "arm":
            stats = _build_arm(args, output, tarballs_dir)
        else:
            stats = _build_riscv(args, output, tarballs_dir)
    except (
        ArchiveError,
        RiscvArchiveError,
        SpecError,
        CheriotError,
        GenerationError,
        OSError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"Generated {stats.instructions} instruction pages")
    print(f"Generated {stats.registers} register pages")
    if args.arch == "riscv":
        print(f"Generated {stats.extensions} extension pages")
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


if __name__ == "__main__":
    raise SystemExit(main())
