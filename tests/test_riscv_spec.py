"""Tests for loading the RISC-V Unified Database resolved specification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from refsite.riscv_spec import (
    SpecError,
    describe_defined_by,
    find_spec_root,
    load_spec,
    parse_location_ranges,
)

ADD_YAML = """\
kind: instruction
name: add
long_name: Integer add
description: |
  Add the value in xs1 to xs2, and store the result in xd.
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
"""

MSTATUS_YAML = """\
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
  SD:
    location_rv32: 31
    location_rv64: 63
    long_name: State Dirty
    description: Whether state is dirty.
    type: RO
    reset_value: 0
  MIE:
    location: 3
    description: Machine interrupt enable.
    type: RW
    reset_value: 0
"""

EXTENSION_YAML = """\
kind: extension
name: I
long_name: Base integer ISA (RV32I or RV64I)
type: unprivileged
description: Base integer instructions.
versions:
  - version: '2.1.0'
    state: ratified
    ratification_date: '2019-06'
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_spec(root: Path) -> Path:
    write(root / "index.yaml", "- inst/I/add.yaml\n- csr/mstatus.yaml\n- ext/I.yaml\n")
    write(root / "inst" / "I" / "add.yaml", ADD_YAML)
    write(root / "csr" / "mstatus.yaml", MSTATUS_YAML)
    write(root / "ext" / "I.yaml", EXTENSION_YAML)
    return root


class SpecLoadingTests(unittest.TestCase):
    def test_loads_objects_from_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_spec(Path(directory))
            spec = load_spec(root)
            self.assertEqual([item.name for item in spec.instructions], ["add"])
            self.assertEqual([item.name for item in spec.csrs], ["mstatus"])
            self.assertEqual([item.name for item in spec.extensions], ["I"])

            instruction = spec.instructions[0]
            self.assertEqual(instruction.extension, "I")
            self.assertEqual(instruction.defined_by, "I")
            self.assertEqual(instruction.operation, "X[xd] = X[xs1] + X[xs2];")
            self.assertEqual(instruction.encodings[0][1].width, 32)

            csr = spec.csrs[0]
            self.assertEqual(csr.address, 768)
            self.assertEqual(len(csr.fields), 2)
            self.assertEqual(csr.fields[0].location_rv64, "63")

    def test_finds_nested_resolved_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_spec(Path(directory) / "gen" / "resolved_spec" / "_")
            self.assertEqual(find_spec_root(Path(directory)), root)

    def test_missing_spec_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SpecError):
                load_spec(Path(directory))

    def test_overlay_replaces_by_name_and_appends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_spec(Path(directory) / "base")
            overlay = Path(directory) / "overlay"
            write(
                overlay / "inst" / "I" / "add.yaml",
                ADD_YAML.replace("long_name: Integer add", "long_name: Overlay add"),
            )
            write(
                overlay / "ext" / "Zcheri.yaml",
                EXTENSION_YAML.replace("name: I", "name: Zcheri").replace(
                    "long_name: Base integer ISA (RV32I or RV64I)", "long_name: CHERI"
                ),
            )
            spec = load_spec(root, overlay)
            self.assertEqual(spec.instruction_map()["add"].long_name, "Overlay add")
            self.assertIn("Zcheri", spec.extension_map())


class DefinedByTests(unittest.TestCase):
    def test_extension_and_xlen(self) -> None:
        self.assertEqual(
            describe_defined_by({"allOf": [{"xlen": 64}, {"extension": {"name": "Zbb"}}]}),
            "RV64 and Zbb",
        )

    def test_nested_any_of_is_parenthesised(self) -> None:
        node = {
            "anyOf": [
                {"allOf": [{"xlen": 64}, {"extension": {"name": "I"}}]},
                {"allOf": [{"xlen": 32}, {"extension": {"name": "Zilsd"}}]},
            ]
        }
        self.assertEqual(describe_defined_by(node), "(RV64 and I) or (RV32 and Zilsd)")

    def test_one_of_not_param_and_version(self) -> None:
        self.assertEqual(
            describe_defined_by({"oneOf": [{"name": "D"}, {"name": "Zdinx"}]}),
            "one of D, Zdinx",
        )
        self.assertEqual(
            describe_defined_by(
                {"allOf": [{"name": "Zbb"}, {"not": {"name": "Zbkb"}}]}
            ),
            "Zbb and not Zbkb",
        )
        self.assertEqual(
            describe_defined_by(
                {"param": {"name": "VLEN", "greaterThanOrEqual": 32}}
            ),
            "VLEN >= 32",
        )
        self.assertEqual(
            describe_defined_by({"extension": {"name": "Sm", "version": ">= 1.12"}}),
            "Sm (>= 1.12)",
        )


class LocationTests(unittest.TestCase):
    def test_disjoint_ranges(self) -> None:
        self.assertEqual(parse_location_ranges("31|7|30-25|11-8"), ((31, 31), (7, 7), (30, 25), (11, 8)))

    def test_disjoint_variable_bits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "index.yaml", "- inst/X/x.yaml\n")
            write(
                root / "inst" / "X" / "x.yaml",
                ADD_YAML.replace("location: 24-20", "location: 31|25"),
            )
            spec = load_spec(root)
            variable = spec.instructions[0].encodings[0][1].variables[0]
            self.assertEqual(variable.bits, (31, 25))
            self.assertEqual(variable.width, 2)


class ValidationTests(unittest.TestCase):
    def test_duplicate_base_name_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "index.yaml", "- inst/I/add.yaml\n- inst/I/add2.yaml\n")
            write(root / "inst" / "I" / "add.yaml", ADD_YAML)
            write(root / "inst" / "I" / "add2.yaml", ADD_YAML)
            with self.assertRaises(SpecError):
                load_spec(root)

    def test_index_entry_cannot_escape_the_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "spec"
            (root / "inst").mkdir(parents=True)
            write(root / "index.yaml", "- ../outside.yaml\n")
            write(Path(directory) / "outside.yaml", ADD_YAML)
            with self.assertRaises(SpecError):
                load_spec(root)

    def test_object_name_cannot_contain_a_path_separator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "index.yaml", "- inst/I/x.yaml\n")
            write(root / "inst" / "I" / "x.yaml", ADD_YAML.replace("name: add", "name: ../add"))
            with self.assertRaises(SpecError):
                load_spec(root)

    def test_malformed_location_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "index.yaml", "- inst/I/x.yaml\n")
            write(
                root / "inst" / "I" / "x.yaml",
                ADD_YAML.replace("location: 24-20", "location: 20-24"),
            )
            with self.assertRaises(SpecError):
                load_spec(root)

    def test_null_text_fields_become_empty_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "index.yaml", "- inst/I/x.yaml\n")
            write(
                root / "inst" / "I" / "x.yaml",
                ADD_YAML.replace("long_name: Integer add", "long_name: null"),
            )
            spec = load_spec(root)
            self.assertEqual(spec.instructions[0].long_name, "")

    def test_string_boolean_is_not_truthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inst").mkdir()
            write(root / "index.yaml", "- csr/mstatus.yaml\n")
            write(
                root / "csr" / "mstatus.yaml",
                MSTATUS_YAML.replace("writable: true", 'writable: "false"'),
            )
            spec = load_spec(root)
            self.assertFalse(spec.csrs[0].writable)

    def test_missing_index_entry_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inst").mkdir()
            write(root / "index.yaml", "- inst/I/missing.yaml\n")
            with self.assertRaises(SpecError):
                load_spec(root)

    def test_unknown_overlay_kind_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_spec(Path(directory) / "base")
            overlay = Path(directory) / "overlay"
            write(
                overlay / "ext" / "Bad.yaml",
                EXTENSION_YAML.replace("kind: extension", "kind: extensionx"),
            )
            with self.assertRaises(SpecError):
                load_spec(root, overlay)


if __name__ == "__main__":
    unittest.main()
