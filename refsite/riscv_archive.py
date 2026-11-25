"""Locate and extract the RISC-V Unified Database resolved specification.

The Unified Database publishes a single ``resolved_spec.tar.gz`` containing
YAML for every instruction, CSR and extension.  This module mirrors the ARM
archive adapter: pick the newest bundle, extract it once into a cache keyed by
the tarball's name, size and mtime, and return the directory to load.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .riscv_spec import SpecError, find_spec_root

_TARBALL_GLOBS = ("resolved_spec*.tar.gz", "resolved_spec*.tgz", "resolved_spec*.tar")
_VERSION_RE = re.compile(r"(?P<year>\d{4})-(?P<month>\d{1,2})")


class RiscvArchiveError(RuntimeError):
    """Raised when the RISC-V source bundle cannot be found or extracted."""


@dataclass
class ExtractedRiscv:
    """Paths and version information for one extracted bundle."""

    spec_dir: Path
    version: str
    work_dir: Path
    temporary: bool


def _release_key(path: Path) -> tuple[int, int]:
    match = _VERSION_RE.search(path.name)
    if not match:
        return (0, 0)
    return (int(match.group("year")), int(match.group("month")))


def _pick_tarball(tarballs_dir: Path) -> Path:
    if not tarballs_dir.is_dir():
        raise RiscvArchiveError(f"tarball directory not found: {tarballs_dir}")
    exact = tarballs_dir / "resolved_spec.tar.gz"
    if exact.is_file():
        return exact
    candidates: list[Path] = []
    for pattern in _TARBALL_GLOBS:
        candidates.extend(path for path in tarballs_dir.glob(pattern) if path.is_file())
    if not candidates:
        raise RiscvArchiveError(
            "no resolved_spec*.tar.gz found in "
            f"{tarballs_dir}; download it from "
            "https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz"
        )
    return max(candidates, key=lambda path: (_release_key(path), path.name))


def _version_from_name(name: str) -> str:
    match = _VERSION_RE.search(name)
    if match:
        return f"{match.group('year')}.{int(match.group('month')):02d}"
    return "latest"


def _short_revision(text: str) -> str:
    """Use git's usual short form when the sidecar contains a full SHA."""

    return text[:7] if re.fullmatch(r"[0-9a-f]{40}", text) else text


def _sidecar_revision(tarballs_dir: Path, tar_path: Path) -> str | None:
    """Return an explicit revision recorded next to the bundle, if present."""

    candidates = (
        tarballs_dir / f"{tar_path.name}.revision",
        tarballs_dir / "resolved_spec.revision",
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return _short_revision(text.splitlines()[0].strip())
    return None


def _content_revision(tar_path: Path, spec_dir: Path) -> str:
    """Build a reproducible revision label from the bundle itself.

    The tarball does not embed a commit, so use the specification build date
    (the preserved mtime of ``index.yaml``) and a SHA-256 prefix of the bundle.
    """

    digest = hashlib.sha256()
    try:
        with tar_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    try:
        mtime = (spec_dir / "index.yaml").stat().st_mtime
        date = datetime.datetime.fromtimestamp(
            mtime, tz=datetime.timezone.utc
        ).strftime("%Y.%m.%d")
    except OSError:
        date = ""
    short = digest.hexdigest()[:12]
    return f"{date}+{short}" if date else short


def _signature(tar_path: Path) -> dict[str, object]:
    stat = tar_path.stat()
    return {"name": tar_path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _marker_matches(target: Path, signature: dict[str, object]) -> bool:
    marker = target / ".extracted"
    if not marker.is_file():
        return False
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return recorded == signature


def _safe_extract(tar_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    try:
        with tarfile.open(tar_path) as archive:
            members = archive.getmembers()
            for member in members:
                if member.issym() or member.islnk():
                    raise RiscvArchiveError(
                        f"refusing to extract link from {tar_path}: {member.name}"
                    )
                if not (member.isfile() or member.isdir()):
                    raise RiscvArchiveError(
                        f"refusing to extract special file from {tar_path}: {member.name}"
                    )
                resolved = (destination / member.name).resolve()
                if resolved != destination and destination not in resolved.parents:
                    raise RiscvArchiveError(
                        f"archive member escapes the extraction directory: {member.name}"
                    )
            if hasattr(tarfile, "data_filter"):
                archive.extractall(destination, filter="data")
            else:  # pragma: no cover - Python < 3.11.4
                archive.extractall(destination)
    except (OSError, tarfile.TarError) as error:
        raise RiscvArchiveError(f"could not extract {tar_path}: {error}") from error


def extract(tarballs_dir: str | Path = ".", work_dir: str | Path | None = None) -> ExtractedRiscv:
    """Find, extract and locate the resolved specification."""

    tarballs_dir = Path(tarballs_dir)
    tar_path = _pick_tarball(tarballs_dir)
    temporary = work_dir is None
    if work_dir is None:
        work = Path(tempfile.mkdtemp(prefix="riscv-sitegen-"))
    else:
        work = Path(work_dir)
    try:
        work.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RiscvArchiveError(f"could not create work directory {work}: {error}") from error

    target = work / tar_path.name.removesuffix(".tar.gz").removesuffix(".tgz").removesuffix(".tar")
    signature = _signature(tar_path)
    if not _marker_matches(target, signature):
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        target.mkdir(parents=True)
        _safe_extract(tar_path, target)
        try:
            find_spec_root(target)
        except SpecError as error:
            shutil.rmtree(target, ignore_errors=True)
            raise RiscvArchiveError(str(error)) from error
        (target / ".extracted").write_text(json.dumps(signature), encoding="utf-8")

    try:
        spec_dir = find_spec_root(target)
    except SpecError as error:
        raise RiscvArchiveError(str(error)) from error
    version = _sidecar_revision(tarballs_dir, tar_path) or _version_from_name(
        tar_path.name
    )
    if version == "latest":
        version = _content_revision(tar_path, spec_dir) or "latest"
    return ExtractedRiscv(
        spec_dir=spec_dir,
        version=version,
        work_dir=work,
        temporary=temporary,
    )


def cleanup(extracted: ExtractedRiscv) -> None:
    """Remove the temporary extraction directory, if one was created."""

    if extracted.temporary:
        shutil.rmtree(extracted.work_dir, ignore_errors=True)
