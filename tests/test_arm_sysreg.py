"""Unit tests for system-register page selection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from refsite.arm_sysreg import selected_register_files


class SysregSelectionTests(unittest.TestCase):
    def test_follows_links_from_register_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xhtml = root / "xhtml"
            xhtml.mkdir()
            (root / "AArch64-regindex.xml").write_text(
                '<regindex><register_page registerfile="A.xml"/></regindex>',
                encoding="utf-8",
            )
            (xhtml / "A.html").write_text('<a href="B.html">B</a>', encoding="utf-8")
            (xhtml / "B.html").write_text('<a href="ext-c.html">C</a>', encoding="utf-8")
            (xhtml / "ext-c.html").write_text("C", encoding="utf-8")
            (xhtml / "notice.html").write_text("notice", encoding="utf-8")
            self.assertEqual(
                [path.name for path in selected_register_files(root)],
                ["A.html", "B.html", "ext-c.html"],
            )

    def test_missing_index_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "xhtml").mkdir()
            with self.assertRaises(ValueError):
                selected_register_files(root)


if __name__ == "__main__":
    unittest.main()
