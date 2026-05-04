"""print-report 重構的單元測試。"""
from app import _strip_inline_styles


def test_strip_double_quoted_style():
    html = '<p style="color:red;">hi</p>'
    assert _strip_inline_styles(html) == '<p>hi</p>'


def test_strip_single_quoted_style():
    html = "<div style='background:#000'>x</div>"
    assert _strip_inline_styles(html) == '<div>x</div>'


def test_strip_multiple_attributes_keeps_others():
    html = '<a class="link" style="color:red" href="/x">go</a>'
    assert _strip_inline_styles(html) == '<a class="link" href="/x">go</a>'


def test_strip_handles_empty_and_none():
    assert _strip_inline_styles('') == ''
    assert _strip_inline_styles(None) == ''


def test_strip_handles_no_style():
    html = '<p>plain</p>'
    assert _strip_inline_styles(html) == '<p>plain</p>'
