"""Tests for building a complete RISC-V site."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from refsite.riscv_site import RiscvSiteBuilder

HERE = Path(__file__).resolve().parent.parent

FILES = {
    "index.yaml": "- inst/I/add.yaml\n- csr/mstatus.yaml\n- ext/I.yaml\n",
    "inst/I/add.yaml": """\
kind: instruction
name: add
long_name: Integer add
description: Add two integers.
definedBy:
  extension:
    name: I
assembly: xd, xs1, xs2
encoding:
  match: '0000000----------000-----0110011'
  variables:
    - name: xs2
      location: 24-20
    - name: xs1
      location: 19-15
    - name: xd
      location: 11-7
access:
  s: always
  u: always
operation(): |
  X[xd] = X[xs1] + X[xs2];
""",
    "csr/mstatus.yaml": """\
kind: csr
name: mstatus
long_name: Machine Status
address: 768
writable: true
description: Machine status register.
priv_mode: M
length: MXLEN
definedBy:
  extension:
    name: Sm
fields:
  MIE:
    location: 3
    description: Machine interrupt enable.
    type: RW
    reset_value: 0
""",
    "ext/I.yaml": """\
kind: extension
name: I
long_name: Base integer ISA
type: unprivileged
description: Base integer instructions.
versions:
  - version: '2.1.0'
    state: ratified
    ratification_date: '2019-06'
""",
}


class SiteBuildTests(unittest.TestCase):
    def test_builds_expected_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec_dir = Path(directory) / "spec"
            for name, text in FILES.items():
                path = spec_dir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            output = Path(directory) / "build"

            stats = RiscvSiteBuilder(
                spec_dir=spec_dir,
                output_dir=output,
                version="test",
                assets_dir=HERE,
            ).build()

            self.assertEqual(stats.instructions, 1)
            self.assertEqual(stats.registers, 1)
            self.assertEqual(stats.extensions, 1)
            self.assertEqual(stats.listings, 3)

            expected = [
                "index.html",
                "robots.txt",
                "latest_riscv/index.html",
                "latest_riscv/csrindex.html",
                "latest_riscv/extindex.html",
                "latest_riscv/insn/add.html",
                "latest_riscv/csr/mstatus.html",
                "latest_riscv/ext/I.html",
                "static/main.css",
                "pagefind/pagefind-component-ui.js",
            ]
            for name in expected:
                self.assertTrue((output / name).is_file(), name)

            home = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("RISC-V Reference", home)
            self.assertNotIn("PER ARM'S REQUEST", home)

            instruction = (output / "latest_riscv/insn/add.html").read_text(encoding="utf-8")
            self.assertNotIn("PER ARM'S REQUEST", instruction)
            self.assertNotIn("cloudflareinsights", instruction)
            self.assertIn("add xd, xs1, xs2", instruction)
            self.assertIn("Version test", instruction)

            listing = (output / "latest_riscv/index.html").read_text(encoding="utf-8")
            self.assertIn("/static/riscv.css", listing)

            for name in (
                "index.html",
                "latest_riscv/index.html",
                "latest_riscv/csrindex.html",
                "latest_riscv/extindex.html",
            ):
                page = (output / name).read_text(encoding="utf-8")
                self.assertIn('<p class="copyconf">Version test</p>', page, name)
                self.assertIn(
                    '<p class="copyconf">Data from the RISC-V Unified Database', page, name
                )
                self.assertNotIn("CHERIoT extensions", page, name)
                self.assertIn("NOT affiliated", page, name)

    def test_overlay_adds_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec_dir = Path(directory) / "spec"
            for name, text in FILES.items():
                path = spec_dir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            overlay = Path(directory) / "overlay"
            overlay.mkdir()
            (overlay / "ext").mkdir()
            (overlay / "ext" / "Zcheri.yaml").write_text(
                FILES["ext/I.yaml"].replace("name: I", "name: Zcheri"), encoding="utf-8"
            )
            output = Path(directory) / "build"

            stats = RiscvSiteBuilder(
                spec_dir=spec_dir,
                output_dir=output,
                version="test",
                assets_dir=HERE,
                overlay_dir=overlay,
            ).build()

            self.assertEqual(stats.extensions, 2)
            self.assertTrue((output / "latest_riscv/ext/Zcheri.html").is_file())


if __name__ == "__main__":
    unittest.main()
