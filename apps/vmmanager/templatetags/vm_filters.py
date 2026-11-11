"""Template filters for VM manager views."""

import re
from html.parser import HTMLParser

import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Proxmox "Notes" are Markdown that may contain inline HTML (community
# scripts set HTML via qm set -description). We render the Markdown like the
# PVE UI does and then strip the result down to this safe subset.
_ALLOWED_TAGS = frozenset({
    "div", "span", "p", "a", "img", "h1", "h2", "h3", "h4", "h5", "h6",
    "br", "hr", "b", "strong", "i", "em", "del", "s", "sub", "sup",
    "ul", "ol", "li", "blockquote", "code", "pre",
    "table", "thead", "tbody", "tr", "th", "td",
})

_ALLOWED_ATTRS = frozenset({
    "href", "src", "alt", "title", "target", "align", "width", "height", "style",
})

# Void elements: never emit a closing tag for them.
_VOID_TAGS = frozenset({"img", "br", "hr"})

_SIZE_RE = re.compile(r"^\d{1,4}(px|%)?$")
# Only harmless layout properties survive in style="" (no position, no
# background/url(), no overlays).
_STYLE_PROPS = frozenset({"width", "height", "max-width", "max-height", "text-align"})
_STYLE_VALUE_RE = re.compile(r"^(\d{1,4}(\.\d+)?(px|%|em|rem)?|auto|left|right|center)$")


def _clean_style(value):
    kept = []
    for decl in (value or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip().lower()
        if prop in _STYLE_PROPS and _STYLE_VALUE_RE.match(val):
            kept.append(f"{prop}: {val}")
    return "; ".join(kept)


class _Sanitiser(HTMLParser):
    """Strip HTML to a safe subset."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            if tag not in _VOID_TAGS:
                self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        safe_attrs = []
        for name, value in attrs:
            name = name.lower()
            value = value or ""
            if name not in _ALLOWED_ATTRS:
                continue
            if name in ("href", "src") and not re.match(r"^https?://", value, re.I):
                continue
            if name in ("width", "height") and not _SIZE_RE.match(value.strip()):
                continue
            if name == "style":
                value = _clean_style(value)
                if not value:
                    continue
            if name == "target":
                value = "_blank"
            safe_attrs.append(f'{name}="{_escape_attr(value)}"')
        if tag == "a":
            safe_attrs = [a for a in safe_attrs if not a.startswith("target=")]
            safe_attrs += ['target="_blank"', 'rel="noopener noreferrer"']
        attr_str = (" " + " ".join(safe_attrs)) if safe_attrs else ""
        self.parts.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            if tag not in _VOID_TAGS and self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0 or tag in _VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        self.parts.append(_escape_data(data))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def get_output(self):
        return "".join(self.parts)


def _escape_attr(value):
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_data(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Let Markdown inside block HTML (e.g. <div align="center"> ... ## Title)
# be rendered, like the PVE UI (marked.js) does.
_BLOCK_OPEN_RE = re.compile(r"<(div|p|span)\b(?![^>]*\bmarkdown=)", re.I)


def render_notes(value):
    """Markdown (+ inline HTML) -> sanitised HTML string."""
    source = _BLOCK_OPEN_RE.sub(lambda m: f'<{m.group(1)} markdown="1"', value)
    html = markdown.markdown(source, extensions=["extra", "sane_lists"])
    sanitiser = _Sanitiser()
    sanitiser.feed(html)
    sanitiser.close()
    return sanitiser.get_output()


@register.filter(name="safe_html_description")
def safe_html_description(value):
    """Render a VM/CT description (PVE Notes) as sanitised HTML."""
    if not value or not isinstance(value, str):
        return value or ""
    return mark_safe(f'<div class="pve-notes">{render_notes(value)}</div>')
