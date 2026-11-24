"""Jinja rendering helpers.

The adapters provide content fragments (already serialised HTML) and metadata;
the templates own the document shell, navigation chrome and home page.  This
keeps the architecture-specific XSLT/XML work separate from presentation and
makes the templates reusable for the planned RISC-V adapter.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .html_transform import escape_attribute, escape_text
from .model import Page

DOCTYPE_XHTML = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
XHTML_ATTRS = ' xmlns="http://www.w3.org/1999/xhtml"'
XHTML_EXT_ATTRS = ' xmlns="http://www.w3.org/1999/xhtml" xmlns:ext="http://exslt.org/common"'


class Renderer:
    def __init__(
        self,
        templates_dir: str | Path,
        *,
        site_title: str = "Jon's Arm Reference",
        copyright_text: str = "Copyright © 2010-2026 Arm Limited or its affiliates.",
        disclaimer: str = (
            "This site is provided as a community resource and is NOT affiliated "
            "with nor endorsed by Arm Limited."
        ),
        chrome_template: str = "partials/chrome.html",
    ) -> None:
        self.site_title = site_title
        self.copyright_text = copyright_text
        self.disclaimer = disclaimer
        self.environment = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        # Render the shared partials once and strip their trailing newline.
        # Including them directly would insert that newline into the page at
        # the include site, which is not how the published pages are laid out.
        self.chrome_html = self._render(chrome_template).rstrip("\n")
        self.cloudflare_html = self._render("partials/cloudflare.html").rstrip("\n")

    def _render(self, template: str, **context: object) -> str:
        return self.environment.get_template(template).render(**context)

    def instruction_page(
        self,
        *,
        title: str,
        description: str,
        content_html: str,
        version: str,
    ) -> Page:
        head_html = self._render(
            "head/instruction.html",
            title=escape_text(title),
            description=escape_attribute(description),
            site_title=escape_text(self.site_title),
        ).rstrip("\n")
        html = self._render(
            "page.html",
            doctype=DOCTYPE_XHTML,
            html_attrs=XHTML_ATTRS,
            head_html=head_html,
            chrome_html=self.chrome_html,
            cloudflare_html=self.cloudflare_html,
            content_html=content_html,
            version=escape_text(version),
            copyright_text=escape_text(self.copyright_text),
            disclaimer=escape_text(self.disclaimer),
        )
        return Page(path="", html=html, title=title, description=description, kind="instruction")

    def sysreg_page(
        self,
        *,
        title: str,
        description: str,
        content_html: str,
        version: str,
    ) -> Page:
        head_html = self._render(
            "head/sysreg.html",
            title=escape_text(title),
            description=escape_attribute(description),
            site_title=escape_text(self.site_title),
        ).rstrip("\n")
        html = self._render(
            "page.html",
            doctype=DOCTYPE_XHTML,
            html_attrs=XHTML_EXT_ATTRS,
            head_html=head_html,
            chrome_html=self.chrome_html,
            cloudflare_html=self.cloudflare_html,
            content_html=content_html,
            version=escape_text(version),
            copyright_text=escape_text(self.copyright_text),
            disclaimer=escape_text(self.disclaimer),
        )
        return Page(path="", html=html, title=title, description=description, kind="sysreg")

    def listing_page(
        self,
        *,
        title: str,
        topbar_html: str,
        listing_html: str,
        extra_newlines: int = 0,
    ) -> Page:
        head_html = self._render(
            "head/listing.html", title=escape_text(title), site_title=escape_text(self.site_title)
        ).rstrip("\n")
        html = self._render(
            "listing.html",
            doctype=DOCTYPE_XHTML,
            html_attrs=XHTML_ATTRS,
            head_html=head_html,
            chrome_html=self.chrome_html,
            cloudflare_html=self.cloudflare_html,
            topbar_html=topbar_html,
            listing_html=listing_html,
            extra_newlines=extra_newlines,
        )
        return Page(path="", html=html, title=title, kind="listing")

    def home_page(
        self,
        *,
        site_title: str,
        site_description: str,
        instruction_links: list[dict[str, str]],
        register_links: list[dict[str, str]],
        contact_url: str,
        site_description_paragraph: str | None = None,
    ) -> Page:
        html = self._render(
            "home.html",
            site_title=escape_text(site_title),
            site_description=escape_attribute(site_description),
            site_description_paragraph=escape_text(
                site_description_paragraph if site_description_paragraph is not None else site_description
            ),
            instruction_links=[
                {"href": escape_attribute(link["href"]), "label": escape_text(link["label"])}
                for link in instruction_links
            ],
            register_links=[
                {"href": escape_attribute(link["href"]), "label": escape_text(link["label"])}
                for link in register_links
            ],
            contact_url=escape_attribute(contact_url),
            cloudflare_html=self.cloudflare_html,
        )
        return Page(path="index.html", html=html, title=site_title, description=site_description, kind="home")
