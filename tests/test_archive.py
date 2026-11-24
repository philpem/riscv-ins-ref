"""Unit tests for the archive discovery and extraction layer."""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from refsite import archive


def _make_tar(path: Path, files: dict[str, bytes], mtime: int | None = None) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            if mtime is not None:
                info.mtime = mtime
            tar.addfile(info, io.BytesIO(data))


class ArchiveTests(unittest.TestCase):
    def test_pick_prefers_preview_over_md_for_same_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ISA_A64_xml_A_profile-2026-09_md.tar.gz").write_bytes(b"old")
            preview = root / "ISA_A64_xml_A_profile-2026-09.tar.gz"
            preview.write_bytes(b"new")
            self.assertEqual(
                archive._pick_tarball(root, "ISA_A64_xml_A_profile-*.tar.gz"),
                preview,
            )

    def test_pick_prefers_later_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ISA_A64_xml_A_profile-2026-09.tar.gz").write_bytes(b"old")
            newer = root / "ISA_A64_xml_A_profile-2026-12.tar.gz"
            newer.write_bytes(b"new")
            self.assertEqual(
                archive._pick_tarball(root, "ISA_A64_xml_A_profile-*.tar.gz"),
                newer,
            )

    def test_safe_extract_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path = root / "bundle.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("../escaped.txt")
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(archive.ArchiveError):
                archive._safe_extract(tar_path, root / "out")
            self.assertFalse((root / "escaped.txt").exists())

    def test_safe_extract_rejects_special_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path = root / "bundle.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("fifo")
                info.type = tarfile.FIFOTYPE
                tar.addfile(info)
            with self.assertRaises(archive.ArchiveError):
                archive._safe_extract(tar_path, root / "out")

    def test_find_release_dir_prefers_newest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("pkg-2026-06", "pkg-2026-09"):
                release = root / name
                (release / "xhtml").mkdir(parents=True)
                (release / "iform.xsl").write_text("", encoding="utf-8")
            self.assertEqual(
                archive._find_release_dir(root, "iform.xsl"),
                root / "pkg-2026-09",
            )

    def test_find_release_dir_prefers_preview_for_same_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("pkg-2026-09_md", "pkg-2026-09"):
                release = root / name
                (release / "xhtml").mkdir(parents=True)
                (release / "iform.xsl").write_text("", encoding="utf-8")
            self.assertEqual(
                archive._find_release_dir(root, "iform.xsl"),
                root / "pkg-2026-09",
            )

    def test_cache_is_invalidated_when_tarball_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path = root / "pkg-2026-09.tar.gz"
            work = root / "work"
            _make_tar(
                tar_path,
                {
                    "pkg-2026-09/xhtml/page.html": b"first",
                    "pkg-2026-09/iform.xsl": b"",
                },
            )
            target = archive._ensure_extracted(tar_path, work)
            page = target / "pkg-2026-09" / "xhtml" / "page.html"
            self.assertEqual(page.read_text(encoding="utf-8"), "first")

            _make_tar(
                tar_path,
                {
                    "pkg-2026-09/xhtml/page.html": b"second version",
                    "pkg-2026-09/iform.xsl": b"",
                },
            )
            os.utime(tar_path, None)
            archive._ensure_extracted(tar_path, work)
            self.assertEqual(page.read_text(encoding="utf-8"), "second version")

    def test_extract_rejects_mismatched_release_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a64 = root / "ISA_A64_xml_A_profile-2026-09.tar.gz"
            sysreg = root / "SysReg_xml_A_profile-2026-08.tar.gz"
            _make_tar(
                a64,
                {
                    "a64-2026-09/xhtml/page.html": b"",
                    "a64-2026-09/iform.xsl": b"",
                },
            )
            _make_tar(
                sysreg,
                {
                    "sysreg-2026-08/xhtml/page.html": b"",
                    "sysreg-2026-08/one_register.xsl": b"",
                },
            )
            with self.assertRaises(archive.ArchiveError):
                archive.extract(root, root / "work")


if __name__ == "__main__":
    unittest.main()
