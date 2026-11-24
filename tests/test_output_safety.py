"""Unit tests for rendering and output-path safety."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate import GenerationError, _validate_output
from refsite.render import Renderer
from refsite.site import SiteBuilder

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


class RenderTests(unittest.TestCase):
    def test_home_page_escapes_configuration_values(self) -> None:
        renderer = Renderer(TEMPLATES)
        page = renderer.home_page(
            site_title="A & B",
            site_description='D "quote"',
            instruction_links=[{"href": '/x?a=1&b=2', "label": "L & M"}],
            register_links=[],
            contact_url="https://example.com/?a=1&b=2",
        )
        self.assertIn("A &amp; B", page.html)
        self.assertIn("D &quot;quote&quot;", page.html)
        self.assertIn("L &amp; M", page.html)
        self.assertIn("/x?a=1&amp;b=2", page.html)

    def test_instruction_page_escapes_metadata(self) -> None:
        renderer = Renderer(TEMPLATES)
        page = renderer.instruction_page(
            title="A & B",
            description='D "quote"',
            content_html="<p>content</p>",
            version="1 & 2",
        )
        self.assertIn("A &amp; B", page.html)
        self.assertIn("D &quot;quote&quot;", page.html)
        self.assertIn("Version 1 &amp; 2", page.html)


class OutputSafetyTests(unittest.TestCase):
    def test_validate_output_rejects_source_tree(self) -> None:
        with self.assertRaises(GenerationError):
            _validate_output(Path("."), Path("."))

    def test_validate_output_allows_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _validate_output(root / "build", root)

    def test_builder_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder = SiteBuilder(
                a64_dir=root,
                sysreg_dir=root,
                output_dir=root / "out",
                version="2026.09",
                assets_dir=root,
                templates_dir=TEMPLATES,
            )
            with self.assertRaises(ValueError):
                builder._write("../escaped.html", "x")


if __name__ == "__main__":
    unittest.main()
