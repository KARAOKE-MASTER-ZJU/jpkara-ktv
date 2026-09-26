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
