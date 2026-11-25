"""Tests for output post-processing helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from refsite.output import apply_base_url


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BaseUrlTests(unittest.TestCase):
    def test_prefixes_root_relative_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            write(
                output / "index.html",
                '<a href="/latest_riscv/index.html">i</a>'
                '<script src="/static/pagefind.js"></script>'
                '<a href="https://example.com/">e</a>'
                '<a href="//cdn.example/x.js">c</a>'
                '<a href="relative.html">r</a>',
            )
            write(output / "static" / "main.css", "a{src:url(/static/font.woff2)}")
            write(
                output / "pagefind" / "pagefind-component-ui.js",
                'const bundle = "/pagefind/";',
            )
            write(output / "robots.txt", "User-agent: *\nAllow: /\n")
            font = output / "static" / "font.woff2"
            font.parent.mkdir(parents=True, exist_ok=True)
            font.write_bytes(b"\x00\x01\x80binary")

            changed = apply_base_url(output, "/riscv-ins-ref")

            self.assertEqual(changed, 4)
            self.assertEqual(font.read_bytes(), b"\x00\x01\x80binary")
            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/riscv-ins-ref/latest_riscv/index.html"', html)
            self.assertIn('src="/riscv-ins-ref/static/pagefind.js"', html)
            self.assertIn('href="https://example.com/"', html)
            self.assertIn('href="//cdn.example/x.js"', html)
            self.assertIn('href="relative.html"', html)
            css = (output / "static" / "main.css").read_text(encoding="utf-8")
            self.assertIn("url(/riscv-ins-ref/static/font.woff2)", css)
            component = (output / "pagefind" / "pagefind-component-ui.js").read_text(
                encoding="utf-8"
            )
            self.assertIn('"/riscv-ins-ref/pagefind/"', component)
            robots = (output / "robots.txt").read_text(encoding="utf-8")
            self.assertEqual(robots, "User-agent: *\nAllow: /riscv-ins-ref/\n")

    def test_second_application_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            write(output / "index.html", '<a href="/latest_riscv/index.html">i</a>')
            write(output / "static" / "main.css", "a{src:url(/static/font.woff2)}")
            write(
                output / "pagefind" / "pagefind-component-ui.js",
                'const bundle = "/pagefind/";',
            )
            write(output / "robots.txt", "User-agent: *\nAllow: /\n")

            self.assertGreater(apply_base_url(output, "/riscv-ins-ref"), 0)
            self.assertEqual(apply_base_url(output, "/riscv-ins-ref"), 0)

            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/riscv-ins-ref/latest_riscv/index.html"', html)
            self.assertNotIn("/riscv-ins-ref/riscv-ins-ref/", html)
            component = (output / "pagefind" / "pagefind-component-ui.js").read_text(
                encoding="utf-8"
            )
            self.assertEqual(component.count("/riscv-ins-ref/pagefind/"), 1)

    def test_root_and_empty_are_no_ops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            write(output / "index.html", '<a href="/latest_riscv/index.html">i</a>')
            write(output / "robots.txt", "User-agent: *\nAllow: /\n")
            for base_url in ("", "/"):
                self.assertEqual(apply_base_url(output, base_url), 0)
                self.assertIn('href="/latest_riscv/index.html"', (output / "index.html").read_text())
                self.assertEqual(
                    (output / "robots.txt").read_text(encoding="utf-8"),
                    "User-agent: *\nAllow: /\n",
                )


if __name__ == "__main__":
    unittest.main()
