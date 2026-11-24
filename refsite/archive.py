"""Locate, extract and validate the ARM reference tarballs.

The two tarballs that contain the material used by the website are the A64
instruction XML bundle and the system-register XML bundle.  Each tarball wraps
a release directory which in turn contains ``xhtml/`` (pre-generated pages)
and the XSLT used to generate those pages.  Some A64 bundles also contain an
older release directory; the highest release identifier wins.
"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

RELEASE_RE = re.compile(r"(?P<year>\d{4})-(?P<month>\d{2})(?:_(?P<kind>[a-z]+))?")


class ArchiveError(RuntimeError):
    pass


@dataclass
class Extracted:
    a64_dir: Path
    sysreg_dir: Path
    version: str
    work_dir: Path
    temporary: bool


def _release_score(path: Path) -> tuple[int, int, int]:
    """Score a release by the identifier in its own directory name.

    Only the final component is considered: extraction roots are named after
    the tarball (which already contains the release date), so scoring the
    whole path would give every nested release the same score and could pick
    an older sibling directory.
    """

    best = (0, 0, 0)
    for match in RELEASE_RE.finditer(path.name):
        # Prefer an unsuffixed Preview release over a suffixed ``_md``/``_mc``
        # review release published under the same date.
        kind = 0 if match.group("kind") is None else -1
        score = (int(match.group("year")), int(match.group("month")), kind)
        best = max(best, score)
    return best


def _version_from_name(name: str) -> str | None:
    match = RELEASE_RE.search(name)
    if not match:
        return None
    return f"{match.group('year')}.{match.group('month')}"


def _pick_tarball(tarballs_dir: Path, pattern: str) -> Path:
    candidates = sorted(tarballs_dir.glob(pattern))
    if not candidates:
        raise ArchiveError(f"no tarball matching {pattern!r} in {tarballs_dir}")

    def score(path: Path) -> tuple[int, int, int]:
        year, month, kind = _release_score(Path(path.name))
        # The unsuffixed "Preview" bundles contain newer architecture content
        # than the `_md`/`_mc` review bundles published under the same date, so
        # prefer them when both are available.  A later date still wins.
        return (year, month, 0 if kind == 0 else -1)

    return max(candidates, key=score)


def _tar_signature(tar_path: Path) -> dict[str, int | str]:
    stat = tar_path.stat()
    return {"name": tar_path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _write_marker(marker: Path, tar_path: Path) -> None:
    marker.write_text(
        json.dumps(_tar_signature(tar_path), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _marker_matches(marker: Path, tar_path: Path) -> bool:
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data == _tar_signature(tar_path)


def _safe_extract(tar_path: Path, destination: Path) -> None:
    """Extract a tarball without allowing paths to escape *destination*."""

    destination = destination.resolve()
    with tarfile.open(tar_path, "r:*") as archive:
        members = []
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                # The ARM bundles do not need links; skipping them avoids a
                # class of path-traversal attacks through link targets.
                continue
            if not (member.isfile() or member.isdir()):
                raise ArchiveError(
                    f"unsupported member type in {tar_path.name}: {member.name}"
                )
            target = (destination / member.name).resolve()
            if target != destination and destination not in target.parents:
                raise ArchiveError(f"unsafe path in {tar_path.name}: {member.name}")
            members.append(member)
        if hasattr(tarfile, "data_filter"):
            archive.extractall(destination, members=members, filter="data")
        else:
            archive.extractall(destination, members=members)


def _find_release_dir(root: Path, marker: str) -> Path:
    """Find the newest directory below *root* that looks like a release."""

    candidates = []
    for marker_path in root.rglob(marker):
        release_dir = marker_path.parent
        if (release_dir / "xhtml").is_dir():
            candidates.append(release_dir)
    if not candidates:
        raise ArchiveError(f"could not find a release directory containing {marker} below {root}")
    return max(candidates, key=lambda path: (_release_score(path), str(path)))


def _ensure_extracted(tar_path: Path, work_dir: Path) -> Path:
    target = work_dir / tar_path.name.removesuffix(".tar.gz")
    marker = target / ".extracted"
    if marker.is_file():
        if _marker_matches(marker, tar_path):
            return target
        # The tarball was replaced.  A stale extraction must be rebuilt even
        # though it still contains an xhtml directory.
        shutil.rmtree(target)
    if target.is_symlink():
        target.unlink()
    if target.exists():
        # Reuse an extraction made by hand, provided it is complete.  The
        # marker records the tarball signature for subsequent runs.
        if any(path.is_dir() and path.name == "xhtml" for path in target.rglob("xhtml")):
            _write_marker(marker, tar_path)
            return target
        shutil.rmtree(target)
    target.mkdir(parents=True)
    _safe_extract(tar_path, target)
    _write_marker(marker, tar_path)
    return target


def extract(
    tarballs_dir: str | Path = ".",
    work_dir: str | Path | None = None,
    *,
    reuse: bool = True,
) -> Extracted:
    """Extract the A64 and SysReg tarballs and return their release roots.

    If *work_dir* is omitted a temporary directory is used.  The caller is
    responsible for calling :func:`cleanup` when it is done with a temporary
    extraction.
    """

    tarballs_dir = Path(tarballs_dir).resolve()
    a64_tar = _pick_tarball(tarballs_dir, "ISA_A64_xml_A_profile-*.tar.gz")
    sysreg_tar = _pick_tarball(tarballs_dir, "SysReg_xml_A_profile-*.tar.gz")

    a64_version = _version_from_name(a64_tar.name)
    sysreg_version = _version_from_name(sysreg_tar.name)
    if a64_version and sysreg_version and a64_version != sysreg_version:
        raise ArchiveError(
            "A64 and SysReg tarballs are from different releases "
            f"({a64_version} and {sysreg_version}); use matching releases"
        )

    temporary = work_dir is None
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="armref-sitegen-", dir=tempfile.gettempdir()))
    else:
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    if reuse:
        a64_root = _ensure_extracted(a64_tar, work_dir)
        sysreg_root = _ensure_extracted(sysreg_tar, work_dir)
    else:
        a64_root = work_dir / a64_tar.name.removesuffix(".tar.gz")
        sysreg_root = work_dir / sysreg_tar.name.removesuffix(".tar.gz")
        for target in (a64_root, sysreg_root):
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
        _safe_extract(a64_tar, a64_root)
        _safe_extract(sysreg_tar, sysreg_root)

    a64_dir = _find_release_dir(a64_root, "iform.xsl")
    sysreg_dir = _find_release_dir(sysreg_root, "one_register.xsl")
    version = a64_version or sysreg_version or "unknown"
    return Extracted(a64_dir=a64_dir, sysreg_dir=sysreg_dir, version=version, work_dir=work_dir, temporary=temporary)


def cleanup(extracted: Extracted) -> None:
    if extracted.temporary:
        shutil.rmtree(extracted.work_dir, ignore_errors=True)
