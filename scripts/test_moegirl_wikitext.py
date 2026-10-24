"""Offline DOM fixtures; this is not evidence of live site access."""
import os
import tempfile
import unittest

from moegirl_wikitext import ROOT, export_page, source_text, valid_url


class SourceTests(unittest.TestCase):
    def test_reject_section_and_other_host(self):
        for url in ("https://example.com/Song", "https://zh.moegirl.org.cn/index.php?title=Song&section=1&action=edit"):
            with self.assertRaises(ValueError):
                valid_url(url)

    def test_browser(self):
        from playwright.sync_api import sync_playwright
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "browsers"))
        with tempfile.TemporaryDirectory(prefix="ktv-browser-test-") as profile, sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(profile, channel="chromium", headless=True)
            try:
                page = context.pages[0]
                base = "https://zh.moegirl.org.cn/TestSong"
                edit = "https://zh.moegirl.org.cn/index.php?title=TestSong&action=edit"
                requests = []
                def handler(route):
                    requests.append(route.request.url)
                    self.assertEqual(route.request.method, "GET")
                    if route.request.url == base:
                        route.fulfill(body='<a id="ca-edit" href="/index.php?title=TestSong&amp;action=edit">source</a>', content_type="text/html")
                    elif route.request.url == edit:
                        route.fulfill(body='<textarea id="wpTextbox1">{{LyricsKai\n|charas=测试甲；\n|original=@1测试\n}}</textarea>', content_type="text/html; charset=utf-8")
                    else:
                        route.abort()
                context.route("**/*", handler)
                page.goto(base)
                self.assertIsNone(source_text(page))
                value, url = export_page(page, base, 5)
                self.assertIn("|charas=测试甲；", value)
                self.assertNotIn("textarea", value)
                self.assertEqual(url, edit)
                self.assertEqual(requests, [base, edit])
                page.locator("textarea").fill("")
                with self.assertRaises(ValueError):
                    source_text(page)
                page.set_content('<h1>Login required</h1>')
                self.assertIsNone(source_text(page))
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
