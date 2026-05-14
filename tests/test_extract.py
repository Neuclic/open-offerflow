from __future__ import annotations

import pytest

from offerflow.errors import OfferFlowError
from offerflow.extract import extract_html_to_markdown


def test_extract_html_to_markdown_keeps_visible_text():
    markdown = extract_html_to_markdown("<html><body><h1>Title</h1><script>hidden()</script><p>Hello <b>OfferFlow</b></p></body></html>")

    assert "Title" in markdown
    assert "Hello OfferFlow" in markdown
    assert "hidden" not in markdown


def test_extract_html_to_markdown_rejects_empty_html():
    with pytest.raises(OfferFlowError):
        extract_html_to_markdown("<html><script>hidden()</script></html>")
