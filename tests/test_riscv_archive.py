"""Tests for extracting the RISC-V resolved specification bundle."""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from refsite.riscv_archive import RiscvArchiveError, cleanup, extract


def make_bundle(directory: Path, *, name: str = "resolved_spec-2026-11.tar.gz") -> Path:
    root = directory / "src" / "gen" / "resolved_spec" / "_"
    (root / "inst" / "I").mkdir(parents=True, exist_ok=True)
    (root / "index.yaml").write_text("- inst/I/add.yaml\n", encoding="utf-8")
    (root / "inst" / "I" / "add.yaml").write_text("kind: instruction\nname: add\n", encoding="utf-8")
    tar_path = directory / name
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(root.parents[1], arcname="gen")
    return tar_path


class ArchiveTests(unittest.TestCase):
    def test_extracts_and_finds_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base)
            work = base / "work"
            extracted = extract(base, work)
            try:
                self.assertEqual(extracted.version, "2026.11")
                self.assertEqual(extracted.spec_dir.name, "_")
                self.assertTrue((extracted.spec_dir / "index.yaml").is_file())
                self.assertTrue((work / "resolved_spec-2026-11" / ".extracted").is_file())
            finally:
                cleanup(extracted)

    def test_reuses_extracted_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base)
            work = base / "work"
            first = extract(base, work)
            second = extract(base, work)
            self.assertEqual(first.spec_dir, second.spec_dir)

    def test_missing_bundle_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RiscvArchiveError):
                extract(Path(directory), Path(directory) / "work")

    def test_picks_newest_release_numerically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base, name="resolved_spec-2026-9.tar.gz")
            make_bundle(base, name="resolved_spec-2026-10.tar.gz")
            extracted = extract(base, base / "work")
            self.assertEqual(extracted.version, "2026.10")

    def test_sidecar_revision_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base, name="resolved_spec.tar.gz")
            (base / "resolved_spec.revision").write_text(
                "5d1ded1f93ab36d3bb6720880a3d12d1d5a8c67e\n", encoding="utf-8"
            )
            extracted = extract(base, base / "work")
            self.assertEqual(extracted.version, "5d1ded1")

    def test_content_revision_falls_back_to_date_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base, name="resolved_spec.tar.gz")
            extracted = extract(base, base / "work")
            self.assertRegex(extracted.version, r"^\d{4}\.\d{2}\.\d{2}\+[0-9a-f]{12}$")

    def test_temporary_work_dir_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_bundle(base)
            extracted = extract(base)
            work = extracted.work_dir
            self.assertTrue(work.is_dir())
            cleanup(extracted)
            self.assertFalse(work.exists())

    def test_invalid_layout_is_not_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "src" / "bad"
            root.mkdir(parents=True)
            (root / "x.yaml").write_text("kind: instruction\nname: x\n", encoding="utf-8")
            tar_path = base / "resolved_spec-2026-11.tar.gz"
            with tarfile.open(tar_path, "w:gz") as archive:
                archive.add(root, arcname="bad")
            work = base / "work"
            with self.assertRaises(RiscvArchiveError):
                extract(base, work)
            self.assertFalse((work / "resolved_spec-2026-11").exists())

    def test_traversal_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tar_path = base / "resolved_spec.tar.gz"
            payload = b"kind: instruction\nname: x\n"
            info = tarfile.TarInfo("../escape.yaml")
            info.size = len(payload)
            with tarfile.open(tar_path, "w:gz") as archive:
                archive.addfile(info, io.BytesIO(payload))
            with self.assertRaises(RiscvArchiveError):
                extract(base, base / "work")


if __name__ == "__main__":
    unittest.main()
