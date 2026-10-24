#!/usr/bin/env python3
"""Read full-page Moegirl source using a native, persistent Linux browser.

Never submits edits, calls denied APIs, or exports authentication credentials.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, unquote, urljoin, urlsplit


ROOT = Path.home() / ".local/share/ktv-playwright"


def page_title(url):
    parts = urlsplit(url)
    title = parse_qs(parts.query).get("title", [unquote(parts.path).lstrip("/")])[0]
    return title.replace("_", " ")


def valid_url(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not (host == "moegirl.org.cn" or host.endswith(".moegirl.org.cn")):
        raise ValueError("Use an HTTPS moegirl.org.cn article URL.")
    query = parse_qs(parts.query, keep_blank_values=True)
    if "section" in query or query.get("action", ["view"])[0] not in ("view", "edit"):
        raise ValueError("Use a full article URL, not a section or another action.")
    return url


def source_text(page):
    """Return only an actual full-page source textarea's value, never HTML."""
    if "section" in parse_qs(urlsplit(page.url).query, keep_blank_values=True):
        raise ValueError("Refusing a section-only source editor.")
    editor = page.locator("textarea#wpTextbox1")
    if editor.count() != 1:
        return None
    value = editor.input_value()
    if not value.strip():
        raise ValueError("Source editor is empty; refusing to save.")
    return value


def export_page(page, url, timeout):
    expected = page_title(url)
    accepted = {expected}
    # Wiki redirects may change a Japanese song title to a Chinese canonical
    # title. Accept the initial article's canonical identity, never a login page.
    if urlsplit(page.url).hostname == urlsplit(url).hostname:
        config = page.evaluate("""() => window.mw?.config ? {
            name: mw.config.get('wgPageName'), ns: mw.config.get('wgNamespaceNumber')
        } : null""")
        if config and config.get("ns") == 0 and config.get("name"):
            accepted.add(config["name"].replace("_", " "))
            accepted.add(page_title(page.url))
    attempted = set()
    deadline = time.monotonic() + timeout
    print("等待完整源码。若需要，请在浏览器手动登录，然后返回歌曲页面；不会提交编辑。", flush=True)
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError("Browser closed before source was available.")
        # All polling is local DOM inspection, not repeated HTTP requests.
        here = page.url
        if urlsplit(here).hostname == urlsplit(url).hostname and page_title(here) in accepted:
            text = source_text(page)
            if text is not None:
                return text, here
            link = page.locator("a#ca-edit, #ca-edit a, a#ca-viewsource, #ca-viewsource a").first
            if link.count():
                href = link.get_attribute("href")
                target = urljoin(here, href or "")
                if href and target not in attempted:
                    valid_url(target)
                    if page_title(target) not in accepted:
                        raise RuntimeError("Source link points to a different article.")
                    attempted.add(target)
                    response = page.goto(target, wait_until="domcontentloaded", timeout=45000)
                    if response and response.status in (403, 429):
                        raise RuntimeError(f"Site denied source navigation (HTTP {response.status}); stopped.")
        page.wait_for_timeout(1000)
    raise RuntimeError("No full-page source editor found before timeout; no output was saved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Full song article URL")
    parser.add_argument("-o", "--output", type=Path, default=Path("lyrics.wiki"))
    parser.add_argument("--login", action="store_true", help="Open browser for manual login; close window to finish")
    parser.add_argument("--headless", action="store_true", help="Reuse a working session without a window")
    parser.add_argument("--profile", type=Path, default=ROOT / "profile")
    parser.add_argument("--timeout", type=int, default=300, help="Source/login wait in seconds")
    args = parser.parse_args()
    valid_url(args.url)
    if args.login and args.headless:
        parser.error("--login needs a visible browser")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    output = args.output.resolve()
    metadata = output.with_suffix(output.suffix + ".json")
    if not args.login and (output.exists() or metadata.exists()):
        parser.error("Output or sidecar already exists; choose another -o path")
    os.umask(0o077)
    args.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "browsers"))
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import Error as BrowserError

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(args.profile.resolve()), channel="chromium", headless=args.headless,
            accept_downloads=False, viewport={"width": 1280, "height": 900},
            args=["--disk-cache-size=33554432", "--media-cache-size=16777216"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            response = page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
            print(f"Browser opened; HTTP {response.status if response else 'n/a'}", flush=True)
            print(f"Page title: {page.title()}", flush=True)
            if args.login:
                print("请在 Linux Chromium 中手动登录；关闭浏览器窗口后保留登录态。", flush=True)
                deadline = time.monotonic() + args.timeout
                while context.pages and time.monotonic() < deadline:
                    try:
                        context.pages[0].wait_for_timeout(1000)
                    except BrowserError:
                        if context.pages:
                            raise
                return 0
            if response and response.status in (403, 429):
                raise RuntimeError(f"Site denied navigation (HTTP {response.status}); stopped.")
            article_info = page.evaluate("""() => ({
                logged_in: !!window.mw?.config?.get('wgUserName'),
                canonical_title: window.mw?.config?.get('wgPageName') || null,
                headings: [...document.querySelectorAll('h2,h3')].map(x => x.textContent.trim())
            })""")
            value, source_url = export_page(page, args.url, args.timeout)
            info = {
                "article_url": args.url, "source_url": source_url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "method": "playwright-full-page-source-editor",
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                "characters": len(value),
                "article": article_info,
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation protects existing user files, including races.
            with output.open("x", encoding="utf-8", newline="") as stream:
                stream.write(value)
            with metadata.open("x", encoding="utf-8") as stream:
                json.dump(info, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            print(f"Saved {len(value)} characters → {output}")
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
