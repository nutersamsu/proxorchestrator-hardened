"""VM/CT Notes rendering: PVE Markdown + inline HTML, sanitised."""

from django.test import SimpleTestCase

from apps.vmmanager.templatetags.vm_filters import render_notes, safe_html_description

NOTES = """<div align="center">
<img src="https://cdn.jsdelivr.net/gh/selfhst/icons/png/debian.png" width="64" alt="Debian">

## server — main box
**Debian 13** · IP **192.0.2.10** · `server.local`
</div>

---

| | |
|---|---|
| Resources | 8 vCPU |

| Service | Address |
|---|---|
| Media server | [:8096](http://192.0.2.10:8096) |

<sub>updated</sub>
"""


class NotesRenderingTests(SimpleTestCase):
    def test_markdown_is_rendered_like_pve(self):
        html = render_notes(NOTES)
        self.assertIn("<h2>server — main box</h2>", html)  # markdown inside <div>
        self.assertIn("<strong>Debian 13</strong>", html)
        self.assertIn("<code>server.local</code>", html)
        self.assertIn("<table>", html)
        self.assertIn("<hr>", html)
        self.assertIn("<sub>updated</sub>", html)
        self.assertIn('<a href="http://192.0.2.10:8096" target="_blank" rel="noopener noreferrer">:8096</a>', html)

    def test_image_keeps_numeric_size(self):
        html = render_notes(NOTES)
        self.assertIn('width="64"', html)
        self.assertNotIn("</img>", html)
        self.assertNotIn('markdown="1"', html)

    def test_dangerous_markup_is_removed(self):
        evil = (
            '<script>alert(1)</script>ok '
            '<img src="https://x/y.png" onerror="alert(2)" width="100;x">'
            '<a href="javascript:alert(3)">j</a> [m](javascript:alert(4)) '
            '<div style="position:fixed;top:0;background:url(https://x)">o</div>'
            '<img src="data:image/png;base64,AAAA"><iframe src="https://x"></iframe>after'
        )
        html = render_notes(evil)
        for bad in ("script", "alert", "onerror", "javascript", "position", "url(",
                    "iframe", "data:", 'width="100;x"'):
            self.assertNotIn(bad, html)
        self.assertIn("ok", html)
        self.assertIn("after", html)

    def test_style_keeps_only_layout_properties(self):
        html = render_notes('<img src="https://x/l.png" style="width:81px;height:112px;position:absolute">')
        self.assertIn('style="width: 81px; height: 112px"', html)

    def test_plain_text_is_escaped(self):
        html = str(safe_html_description("a < b & c"))
        self.assertIn('class="pve-notes"', html)
        self.assertIn("a &lt; b &amp; c", html)
