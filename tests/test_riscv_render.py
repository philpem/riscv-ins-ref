"""Tests for rendering RISC-V content fragments."""

from __future__ import annotations

import dataclasses
import unittest

from refsite.riscv_render import (
    clean_description,
    csr_listing,
    encoding_table,
    extension_members,
    render_csr,
    render_extension,
    render_instruction,
)
from refsite.riscv_spec import (
    Csr,
    CsrField,
    Encoding,
    EncodingVariable,
    Extension,
    ExtensionVersion,
    Instruction,
    Spec,
)

ADD = Instruction(
    name="add",
    long_name="Integer add",
    description="Add the value in xs1 to xs2, and store the result in xd.",
    defined_by="I",
    assembly="xd, xs1, xs2",
    encodings=(
        (
            None,
            Encoding(
                match="0000000----------000-----0110011",
                variables=(
                    EncodingVariable("xs2", ((24, 20),)),
                    EncodingVariable("xs1", ((19, 15),)),
                    EncodingVariable("xd", ((11, 7),)),
                ),
            ),
        ),
    ),
    access=(("s", "always"), ("u", "always")),
    operation="X[xd] = X[xs1] + X[xs2];",
    data_independent_timing=True,
    hints=(),
    pseudoinstructions=(),
    extension="I",
    path="inst/I/add.yaml",
)

MSTATUS = Csr(
    name="mstatus",
    long_name="Machine Status",
    address=768,
    writable=True,
    description="Machine status register.",
    priv_mode="M",
    length="MXLEN",
    defined_by="Sm",
    fields=(
        CsrField(
            name="SD",
            long_name="State Dirty",
            description="Whether state is dirty.",
            location=None,
            location_rv32="31",
            location_rv64="63",
            type_text="RO",
            reset_text="0",
            alias=None,
        ),
        CsrField(
            name="MIE",
            long_name="",
            description="Machine interrupt enable.",
            location="3",
            location_rv32=None,
            location_rv64=None,
            type_text="RW",
            reset_text="0",
            alias=None,
        ),
    ),
    sw_read=None,
    virtual_address=None,
    indirect_address=None,
    indirect_slot=None,
    path="csr/mstatus.yaml",
)

EXTENSION = Extension(
    name="I",
    long_name="Base integer ISA (RV32I or RV64I)",
    type="unprivileged",
    description="Base integer instructions.",
    versions=(ExtensionVersion("2.1.0", "ratified", "2019-06"),),
    path="ext/I.yaml",
)


class InstructionRenderTests(unittest.TestCase):
    def test_assembly_includes_mnemonic(self) -> None:
        _, _, html = render_instruction(ADD, known_extensions={"I"}, known_instructions={"add"})
        self.assertIn(">add xd, xs1, xs2</pre>", html)
        self.assertIn(
            '<pre class="pseudocode" data-pagefind-body="1">add xd, xs1, xs2</pre>',
            html,
        )

    def test_instruction_without_operands_still_shows_mnemonic(self) -> None:
        instruction = dataclasses.replace(ADD, assembly="")
        _, _, html = render_instruction(instruction)
        self.assertIn(
            '<pre class="pseudocode" data-pagefind-body="1">add</pre>',
            html,
        )

    def test_encoding_table_groups_fixed_bits(self) -> None:
        table = encoding_table(ADD.encodings[0][1])
        self.assertIn('<td colspan="7" class="encoding-fixed">0000000</td>', table)
        self.assertIn('class="encoding-variable" title="xs2">xs2</td>', table)
        self.assertIn('data-pagefind-body="1"', table)

    def test_clean_description_removes_asciidoc_scaffolding(self) -> None:
        raw = (
            "<%- if ext?(:S) -%>\nS-mode\n<%- end -%>\n"
            "[[anchor]]\n[NOTE]\n====\n|===\n| A | B\n|===\n"
            "(((index)))\nlatexmath:[x]"
        )
        cleaned = clean_description(raw)
        for marker in ("<%", "[[", "[NOTE]", "|===", "(((", "latexmath:"):
            self.assertNotIn(marker, cleaned)
        self.assertIn("S-mode", cleaned)
        self.assertIn("A — B", cleaned)
        self.assertIn("index", cleaned)

    def test_pagefind_attributes(self) -> None:
        _, _, html = render_instruction(ADD)
        self.assertIn('data-pagefind-body="1"', html)
        self.assertIn('data-pagefind-sort="title:add"', html)
        self.assertIn(
            '<pre class="pseudocode" data-pagefind-body="1">X[xd] = X[xs1] + X[xs2];</pre>',
            html,
        )

    def test_extension_link_only_when_known(self) -> None:
        _, _, html = render_instruction(ADD, known_extensions={"I"})
        self.assertIn('href="../ext/I.html"', html)
        _, _, html = render_instruction(ADD, known_extensions=set())
        self.assertNotIn('href="../ext/I.html"', html)

    def test_access_table_uses_privilege_names(self) -> None:
        _, _, html = render_instruction(ADD)
        self.assertIn("<th>S</th><th>U</th>", html)
        self.assertIn("<td>Always</td>", html)

    def test_rv32_and_rv64_encodings_are_both_rendered(self) -> None:
        instruction = dataclasses.replace(
            ADD,
            encodings=(("RV32", ADD.encodings[0][1]), ("RV64", ADD.encodings[0][1])),
        )
        _, _, html = render_instruction(instruction)
        self.assertEqual(html.count("<h3>RV32</h3>"), 2)
        self.assertEqual(html.count("<h3>RV64</h3>"), 2)


class CsrRenderTests(unittest.TestCase):
    def test_metadata_and_split_bitfield(self) -> None:
        _, _, html = render_csr(MSTATUS)
        self.assertIn("0x300", html)
        self.assertIn("Privilege: M", html)
        self.assertIn("<h3>RV32</h3>", html)
        self.assertIn("<h3>RV64</h3>", html)
        self.assertIn("MIE", html)
        self.assertIn('<table class="fields-table" data-pagefind-body="1">', html)

    def test_field_without_location_does_not_suppress_diagram(self) -> None:
        csr = dataclasses.replace(
            MSTATUS,
            fields=MSTATUS.fields
            + (
                CsrField(
                    name="DERIVED",
                    long_name="",
                    description="Not stored in the CSR.",
                    location=None,
                    location_rv32=None,
                    location_rv64=None,
                    type_text="RO",
                    reset_text="0",
                    alias=None,
                ),
            ),
        )
        _, _, html = render_csr(csr)
        self.assertIn('<table class="encoding-table csr-bitfield">', html)
        self.assertIn("MIE", html)

    def test_idl_values_use_preserved_whitespace_and_alias_is_shown(self) -> None:
        field = dataclasses.replace(
            MSTATUS.fields[1],
            type_text="if (condition) {\n  return CsrFieldType::RW;\n}",
            reset_text="if (reset) {\n  return 0;\n}",
            alias="ALT",
        )
        _, _, html = render_csr(dataclasses.replace(MSTATUS, fields=(field,)))
        self.assertIn('<pre class="field-code">if (condition)', html)
        self.assertIn("<td><code>ALT</code></td>", html)

    def test_xlen_dependent_csr_gets_both_views(self) -> None:
        fields = (
            CsrField("HIGH", "", "", "63", None, None, "RW", "0", None),
            CsrField("LOW", "", "", "3", None, None, "RW", "0", None),
        )
        csr = dataclasses.replace(MSTATUS, length="MXLEN", fields=fields)
        _, _, html = render_csr(csr)
        self.assertIn("<h3>RV32</h3>", html)
        self.assertIn("<h3>RV64</h3>", html)
        self.assertEqual(html.count('title="HIGH"'), 1)
        self.assertEqual(html.count('title="LOW"'), 2)

    def test_listing_links_are_relative(self) -> None:
        spec = Spec(instructions=[ADD], csrs=[MSTATUS], extensions=[EXTENSION])
        self.assertIn('href="csr/mstatus.html"', csr_listing(spec))


class ExtensionRenderTests(unittest.TestCase):
    def test_lists_members(self) -> None:
        _, _, html = render_extension(EXTENSION, instructions=[ADD], csrs=[MSTATUS])
        self.assertIn('href="../insn/add.html"', html)
        self.assertIn('href="../csr/mstatus.html"', html)
        self.assertIn("2.1.0", html)

    def test_empty_extension_explains_itself(self) -> None:
        _, _, html = render_extension(EXTENSION)
        self.assertIn("No instructions or CSRs are directly attributed", html)

    def test_negated_extension_is_not_a_member(self) -> None:
        instruction = dataclasses.replace(
            ADD,
            name="zext.h",
            defined_by_extensions=("Zbb",),
            defined_by_excluded=("Zbkb",),
        )
        zbb = dataclasses.replace(EXTENSION, name="Zbb")
        zbkb = dataclasses.replace(EXTENSION, name="Zbkb")
        spec = Spec(instructions=[instruction], csrs=[], extensions=[zbb, zbkb])
        self.assertEqual(extension_members(spec, zbkb, include_requirements=False), ([], []))
        members, _ = extension_members(spec, zbb, include_requirements=False)
        self.assertEqual([item.name for item in members], ["zext.h"])

    def test_category_extension_inherits_required_members(self) -> None:
        instruction = dataclasses.replace(
            ADD, defined_by_extensions=("Zaamo",), defined_by_excluded=()
        )
        zaamo = dataclasses.replace(EXTENSION, name="Zaamo")
        category = dataclasses.replace(
            EXTENSION, name="A", required_extensions=("Zaamo",)
        )
        spec = Spec(instructions=[instruction], csrs=[], extensions=[category, zaamo])
        members, _ = extension_members(spec, category)
        self.assertEqual([item.name for item in members], ["add"])


if __name__ == "__main__":
    unittest.main()
