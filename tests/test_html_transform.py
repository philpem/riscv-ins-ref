"""Unit tests for the Arm XHTML transformations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lxml import etree

from refsite.html_transform import (
    XHTML,
    _format_field_heading,
    escape_attribute,
    escape_text,
    q,
    transform_instruction,
    transform_sysreg,
)


def _write_xhtml(path: Path, body: str) -> None:
    path.write_text(
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
        f'<html xmlns="{XHTML}"><head><title>x</title></head><body>{body}</body></html>',
        encoding="utf-8",
    )


class TransformTests(unittest.TestCase):
    def test_escape_helpers(self) -> None:
        self.assertEqual(escape_text("a & <b>"), "a &amp; &lt;b&gt;")
        self.assertEqual(escape_attribute('a "b" & c'), "a &quot;b&quot; &amp; c")

    def test_format_field_heading_plain(self) -> None:
        heading = etree.Element(q("h4"))
        heading.text = "FIELD, bit [0]"
        _format_field_heading(heading)
        self.assertEqual(heading.text, "FIELD, bit [0]:\n      ")

    def test_format_field_heading_condition(self) -> None:
        heading = etree.Element(q("h4"))
        heading.text = "PAN, bit [22]"
        condition = etree.SubElement(heading, q("span"))
        condition.set("class", "condition")
        condition.text = "When FEAT_PAN is implemented:"
        _format_field_heading(heading)
        self.assertEqual(heading.text, "PAN, bit [22] ")
        self.assertEqual(condition.text, "when FEAT_PAN is implemented")
        self.assertEqual(condition.tail, ":\n      ")

    def test_transform_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xhtml = root / "foo.html"
            xml = root / "foo.xml"
            _write_xhtml(
                xhtml,
                '<h2 class="instruction-section">FOO</h2>'
                "<p>Subtitle</p>"
                '<p class="aml">Description</p>'
                "<h3>Operation</h3>"
                '<div class="encoding"><h4 class="encoding">Encoding for the 32-bit variant</h4>'
                '<a id="enc"></a><span class="bitdiff"> (cond)</span>'
                '<p class="asm-code">X</p></div>'
                '<img src="diagram.svg"/>',
            )
            xml.write_text(
                "<instruction><desc><authored><para>Long description</para></authored></desc>"
                '<encoding name="enc" label=""/></instruction>',
                encoding="utf-8",
            )
            body, title, description = transform_instruction(xhtml, xml)
            self.assertEqual(title, "FOO")
            self.assertEqual(description, "Long description")
            self.assertIn('data-pagefind-sort="title"', body)
            self.assertIn("<h2>Operation</h2>", body)
            self.assertIn('class="encoding__label"', body)
            self.assertIn("32-bit encoding", body)
            self.assertIn('class="diagram"', body)
            self.assertLess(body.index('class="diagram"'), body.index('src="diagram.svg"'))

    def test_transform_sysreg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xhtml = root / "AArch64-foo.html"
            xml = root / "AArch64-foo.xml"
            _write_xhtml(
                xhtml,
                '<h1 class="register-section">FOO, Foo register</h1>'
                "<p>The FOO characteristics are:</p>"
                "<h2>Purpose</h2><p>Purpose text</p>"
                "<h2>Configuration</h2>"
                '<h4 id="fieldset_x">FIELD, bit [0]</h4>'
                '<div class="access_mechanisms"><h2>Accessing FOO</h2>'
                '<div><h4 class="assembler">MRS &lt;Xt&gt;, FOO</h4></div>'
                '<table class="access_instructions"><tr><th>op0</th></tr>'
                "<tr><td>0b11</td></tr></table></div>",
            )
            xml.write_text(
                "<register_page><reg_short_name>FOO</reg_short_name>"
                "<reg_long_name>Foo register</reg_long_name>"
                "<reg_purpose><purpose_text><para>Purpose text</para></purpose_text></reg_purpose>"
                "</register_page>",
                encoding="utf-8",
            )
            body, title, description = transform_sysreg(xhtml, xml)
            self.assertEqual(title, "FOO")
            self.assertEqual(description, "Purpose text")
            self.assertIn('data-pagefind-sort="title"', body)
            self.assertIn('<p class="insn_subtitle" data-pagefind-body="1">Foo register</p>', body)
            self.assertNotIn("characteristics are", body)
            self.assertIn('<div data-pagefind-body="1">', body)
            self.assertIn("<h3>Configuration</h3>", body)
            self.assertIn("FIELD, bit [0]:", body)
            self.assertIn("Access Instructions", body)
            self.assertIn('class="access_block"', body)
            self.assertIn("(op0 = 0b11)", body)


if __name__ == "__main__":
    unittest.main()
