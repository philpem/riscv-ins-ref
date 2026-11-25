"""Tests for the CHERIoT Sail instruction loader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from refsite.cheriot import (
    EXTENSION_NAME,
    CheriotError,
    apply_cheriot,
    load_cheriot,
)
from refsite.riscv_site import RiscvSiteBuilder
from refsite.riscv_spec import Extension, ExtensionVersion, Spec

HERE = Path(__file__).resolve().parent.parent

MNEMONICS = {
    "CGetPerm": ("cgetperm", "rd, cs1"),
    "CSeal": ("cseal", "cd, cs1, cs2"),
    "CIncAddrImmediate": ("cincaddrimm", "cd, cs1, imm"),
    "LoadCapImm": ("lc", "cd, offset(cs1)"),
    "StoreCapImm": ("sc", "cs2, offset(cs1)"),
}

SAIL = """\
/*! Test description for CGetPerm. */
function clause execute CGetPerm(rd, cs1) = { }
mapping clause encdec = CGetPerm(rd, cs1) <-> 0b1111111 @ 0b00000 @ cs1 @ 0b000 @ rd @ 0b1011011 if (haveXcheri())

/*! Test description for CSeal. */
function clause execute CSeal(cd, cs1, cs2) = { }
mapping clause encdec = CSeal(cd, cs1, cs2) <-> 0b0001011 @ cs2 @ cs1 @ 0b000 @ cd @ 0b1011011 if (haveXcheri())

/*! Test description for CIncAddrImmediate. */
function clause execute CIncAddrImmediate(cd, cs1, imm12) = { }
mapping clause encdec = CIncAddrImmediate(cd, cs1, imm12) <-> imm12 : bits(12) @ cs1 @ 0b001 @ cd @ 0b1011011 if (haveXcheri())

function clause execute LoadCapImm(cd, cs1, offset) = { }
mapping clause encdec = LoadCapImm(cd, cs1, offset) <-> offset : bits(12) @ cs1 @ 0b011 @ cd @ 0b0000011 if (haveXcheri())

function clause execute StoreCapImm(cs2, rs1, off7, off5) = { }
mapping clause encdec = StoreCapImm(cs2, rs1, off7, off5) <-> off7 : bits(7) @ cs2 @ rs1 @ 0b011 @ off5 : bits(5) @ 0b0100011 if (haveXcheri())
"""


def make_repo(root: Path) -> Path:
    source = root / "src"
    source.mkdir(parents=True)
    (source / "cheri_insts.sail").write_text(SAIL, encoding="utf-8")
    return root


def patch_mnemonics():
    return patch.dict("refsite.cheriot._MNEMONICS", MNEMONICS, clear=True)


class ParserTests(unittest.TestCase):
    def test_parses_encodings(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch_mnemonics():
            repo = make_repo(Path(directory))
            extension, instructions = load_cheriot(repo)
            self.assertEqual(extension.name, EXTENSION_NAME)
            self.assertIn("Ibex", extension.description)
            self.assertIn("Kudu", extension.description)
            self.assertEqual(len(instructions), 5)

            by_name = {item.name: item for item in instructions}
            self.assertEqual(
                by_name["cgetperm"].encodings[0][1].match,
                "111111100000-----000-----1011011",
            )
            self.assertEqual(
                by_name["cseal"].encodings[0][1].match,
                "0001011----------000-----1011011",
            )
            self.assertEqual(
                by_name["cincaddrimm"].encodings[0][1].match,
                "-----------------001-----1011011",
            )
            self.assertEqual(
                [variable.name for variable in by_name["cgetperm"].encodings[0][1].variables],
                ["cs1", "rd"],
            )
            self.assertEqual(
                [variable.name for variable in by_name["lc"].encodings[0][1].variables],
                ["offset", "cs1", "cd"],
            )
            sc_offset = next(
                variable
                for variable in by_name["sc"].encodings[0][1].variables
                if variable.name == "offset"
            )
            self.assertEqual(sc_offset.ranges, ((31, 25), (11, 7)))

    def test_missing_source_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CheriotError):
                load_cheriot(Path(directory))


class ApplyTests(unittest.TestCase):
    def test_replaces_and_appends(self) -> None:
        existing = Extension(
            name=EXTENSION_NAME,
            long_name="Old",
            type="unprivileged",
            description="",
            versions=(ExtensionVersion("0", "ratified", ""),),
            path="old",
        )
        spec = Spec(instructions=[], csrs=[], extensions=[existing])
        with tempfile.TemporaryDirectory() as directory, patch_mnemonics():
            apply_cheriot(spec, make_repo(Path(directory)))
        self.assertEqual(len(spec.instructions), 5)
        self.assertEqual([item.name for item in spec.extensions], [EXTENSION_NAME])
        self.assertEqual(spec.extensions[0].long_name, "CHERIoT capability instructions")


class BuildTests(unittest.TestCase):
    def test_site_includes_cheriot_pages(self) -> None:
        spec_files = {
            "index.yaml": "- inst/I/add.yaml\n- ext/I.yaml\n",
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
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            spec_dir = base / "spec"
            for name, text in spec_files.items():
                path = spec_dir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            output = base / "build"
            with patch_mnemonics():
                stats = RiscvSiteBuilder(
                    spec_dir=spec_dir,
                    output_dir=output,
                    version="test",
                    assets_dir=HERE,
                    cheriot_repo=make_repo(base / "cheriot"),
                ).build()

            self.assertEqual(stats.instructions, 6)
            self.assertEqual(stats.extensions, 2)
            self.assertTrue((output / "latest_riscv/insn/cgetperm.html").is_file())
            self.assertTrue((output / "latest_riscv/ext/Xcheriot.html").is_file())
            page = (output / "latest_riscv/ext/Xcheriot.html").read_text(encoding="utf-8")
            self.assertIn("Ibex", page)
            self.assertIn("Kudu", page)
            self.assertIn("CHERIoT extensions from the CHERIoT specification", page)
            self.assertIn('<p class="copyconf">Version test</p>', page)

            listing = (output / "latest_riscv/index.html").read_text(encoding="utf-8")
            self.assertIn("Test description for CGetPerm.", listing)


if __name__ == "__main__":
    unittest.main()
