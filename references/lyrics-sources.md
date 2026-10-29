# Lyrics sources

Read this reference when lyrics are missing. Search by the exact Japanese title plus artist name.

Prefer an official lyric page, booklet, label page, or licensed service. Common indexes:

- [歌ネット / Uta-Net](https://www.uta-net.com/)
- [歌詞検索UtaTen](https://utaten.com/)
- [萌娘百科](https://zh.moegirl.org.cn/)
- [萌娘百科镜像 moegirl.icu](https://moegirl.icu/zh-cn/Mainpage)
- [歌詞検索J-Lyric.net](https://j-lyric.net/)
- [JOYSOUND 歌詞検索](https://www.joysound.com/web/search)
- [PetitLyrics / プチリリ](https://petitlyrics.com/index)
- [ORICON 歌詞検索](https://www.oricon.co.jp/search/result.php?types=lyrics)

Uta-Net → UtaTen → J-Lyric → JOYSOUND → ORICON → PetitLyrics is a practical lyric fallback order. For ACG songs, use 萌娘百科 or `moegirl.icu` early and treat documented song/album information as authoritative; `moegirl.icu` is authoritative but may contain an older snapshot, so only newly changed or time-sensitive details need a current-source check.

Prefer sources without login, CAPTCHA, JavaScript challenges, or aggressive rate limits. On 403, 429, bot-check, Cloudflare, or robots restrictions, switch sources immediately; do not bypass challenges, rotate identities, or hammer the site. Browser-visible content may be usable through the browser tool, but do not build a scraper for a blocked site.

Cross-check suspicious lines against a second source or the official release. Convert the selected text to UTF-8, one sung line per line; remove HTML, ruby/furigana markup, chords, translations, and commentary while preserving meaningful repetitions and punctuation. Never invent missing lyrics. Keep fetched text local and do not reproduce the full lyrics in the response.

## Native Linux browser → full Wikitext

Browser route: in GPT desktop, use the available Computer Use tool directly to open the article and read/copy its full source; in a command-line environment, use Playwright as described below. If Computer Use is unavailable, say so rather than claiming to operate it. Both routes use normal authorized browsing and never submit edits.

When the user requests the normal authenticated browser workflow, use `scripts/moegirl_wikitext.py`. It opens Linux Chromium through Playwright, follows the article's full-page Edit/View-source tab, and reads `textarea#wpTextbox1.value`. It never submits an edit. This preserves `LyricsKai`, `colors`, `charas`, and speaker markers for the ASS API; do not replace this input with rendered/plain lyrics or section-only source. Anonymous `zh.moegirl.org.cn/api.php` returned `action-notallowed: Unauthorized API call` in our test; authenticated API access has not been verified. This helper does not call that API or bypass denied access.

Use a dedicated Playwright virtual environment, a shared Chromium installation, and a private persistent profile outside the skill/repository. Discover or configure these locations on the current machine; do not document a user's installation paths. WSLg can supply the visible Linux window. Do not read/copy the user's Windows browser cookies. Do not commit the profile, credentials, traces, or browser binaries. Browser disk/media cache targets are 32/16 MiB, not a total profile-size guarantee.

```bash
# First use: manually sign in, then close the browser window.
moegirl-wikitext 'https://zh.moegirl.org.cn/歌曲页面' --login
# Subsequent export; existing files are never overwritten.
moegirl-wikitext 'https://zh.moegirl.org.cn/歌曲页面' -o lyrics.wiki
```

The local command is a launcher in `~/.local/bin`; portable invocation is `PATH_TO_VENV/bin/python PATH_TO_SKILL/scripts/moegirl_wikitext.py URL -o lyrics.wiki`. Output includes `lyrics.wiki.json` with source URLs, retrieval time, character count, and SHA-256. `--headless` reuses an already-working session without a window; if login expires, rerun visibly. `--timeout` bounds the wait (default 300 seconds). Only one process may use a given profile at a time. The login command merely allows manual sign-in; its exit status is not proof of authentication.

Live authenticated export was verified on 2026-10-24 for `百億年分のしあわせ` (canonical article `百亿年的幸福`): lyrics heading found, 1,533 characters exported. That skin places `ca-edit` on the anchor itself, so support both `a#ca-edit` and `#ca-edit a` (and the view-source equivalents). Preserve canonical-title redirects when validating source links. The metadata records login presence as a boolean and article headings, never the account name or cookies. A downstream `/api/process` test with 48 aligned lyric events returned 8 characters/8 colors, no unmatched warnings, and preserved times, K tags, and readings; this is evidence for that sample, not a guarantee for all songs.

To install on another Linux machine, create a dedicated Python venv, install `playwright`, then run `PLAYWRIGHT_BROWSERS_PATH="$HOME/.local/share/ktv-playwright/browsers" PATH_TO_VENV/bin/playwright install chromium --no-shell`. Use `playwright install-deps chromium` only if OS libraries are missing. Visible operation needs a Linux desktop/WSLg; do not silently use a headless session for manual login. See [Playwright browser installation](https://playwright.dev/python/docs/browsers) and [persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).

HTTP 403/429 stops export; a missing source editor times out without saving HTML as Wikitext. Do not automate CAPTCHA, change fingerprints, rotate proxies, or repeatedly refresh challenges. If normal authorized browsing cannot expose source, stop and request a user-exported Wikitext file. A fixture test verifies extraction logic, not live Moegirl access; report live success only after actual source export.
