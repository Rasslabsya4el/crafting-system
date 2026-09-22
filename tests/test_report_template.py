"""Focused contract checks for the standalone report shell asset.

The template is a plain HTML/CSS shell now: reporting.py renders the whole
page server-side and fills `{{REPORT_TITLE}}` / `{{REPORT_BODY}}`. There is
no embedded JSON blob and no client-side JavaScript to test here; route
selection uses a CSS-only radio-button tab pattern instead.
"""

from __future__ import annotations

import re
from pathlib import Path


TEMPLATE = Path(__file__).parents[1] / "src" / "craftoracle" / "report_assets" / "template.html"


def test_template_contains_the_two_required_placeholders() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    assert "{{REPORT_TITLE}}" in content
    assert "{{REPORT_BODY}}" in content
    # REPORT_TITLE may appear more than once (<title> and <h1>); REPORT_BODY exactly once.
    assert content.count("{{REPORT_BODY}}") == 1


def test_template_has_no_client_side_script() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    assert "<script" not in content.lower()


def test_template_only_reaches_google_fonts_over_the_network() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    urls = re.findall(r"https?://[^\s'\"()]+", content)
    assert urls, "expected the Google Fonts import to be present"
    for url in urls:
        assert url.startswith("https://fonts.googleapis.com/") or url.startswith("https://fonts.gstatic.com/"), url


def test_template_declares_the_dark_craft_of_exile_style_palette() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    assert "color-scheme: dark" in content
    for token in ("--bg", "--panel", "--frame", "--rare", "--mod", "--added", "--removed"):
        assert token in content, token
    assert "Cinzel" in content  # the serif small-caps heading face named in the brief


def test_template_is_a_complete_html_document() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    assert content.lstrip().lower().startswith("<!doctype html>")
    assert '<html lang="en">' in content
    assert "<title>{{REPORT_TITLE}}</title>" in content
