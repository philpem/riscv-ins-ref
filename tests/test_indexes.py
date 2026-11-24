"""Unit tests for listing extraction."""

from __future__ import annotations

import unittest

from refsite.indexes import _listing_region


class ListingTests(unittest.TestCase):
    def test_listing_region_rewrites_local_links_only(self) -> None:
        document = (
            "<html><body><h1>Title</h1>\n"
            '<div><a href="foo.xml">Foo</a> <a href="https://example.com/bar.xml">Bar</a></div>\n'
            "<hr/></body></html>"
        )
        region = _listing_region(document)
        self.assertIn('href="foo.html"', region)
        self.assertIn('href="https://example.com/bar.xml"', region)
        self.assertNotIn("<hr", region)

    def test_listing_region_requires_terminator(self) -> None:
        with self.assertRaises(ValueError):
            _listing_region("<html><body><h1>Title</h1>\n<div>content</div></body></html>")

    def test_listing_region_rejects_empty_region(self) -> None:
        with self.assertRaises(ValueError):
            _listing_region("<html><body><h1>Title</h1>\n  \n<hr/></body></html>")


if __name__ == "__main__":
    unittest.main()
