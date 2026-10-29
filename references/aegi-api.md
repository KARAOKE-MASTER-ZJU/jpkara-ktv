# Aegisub ASS Tool API

Use this reference for Wikitext-based singer assignment (分词), furigana annotation, or adding Aegisub project video/audio metadata. This is an optional ASS processing stage; it does not replace FA-Kara/YOHANE audio alignment.

- Service: https://aegi.umi-cv.com/
- Source: https://github.com/KARAOKE-MASTER-ZJU/subtitle-moegirl-itool
- Live schema: https://aegi.umi-cv.com/openapi.json
- Local checkout: discover or configure the available `aegisub-tools` checkout. Compare its revision with the service schema before assuming local code matches deployment.

The interface below was verified against the live schema and synthetic ASS requests on 2026-10-23. Refer to the live schema if it changes.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /api/process` | Process ASS; accepts `multipart/form-data`, returns JSON containing ASS text and diagnostics. |
| `POST /api/preview` | Upload `file`; returns `line_count` and `sample` with up to 8 parsed events (`start`, `end`, `style`, `name`, truncated `text`). This is text inspection, not rendered video. |
| `GET /api/config` | Returns the configured `model` string. Query when needed rather than hardcoding a model name. |
| `GET /healthz` | Returns plain text `ok`. |

The tested requests did not require authentication. No API key is needed for the documented public interface.

## Processing fields

Boolean options are form strings `true` / `false`, not a JSON request body.

| Field | Meaning and usual value |
| --- | --- |
| `file` | Aligned source ASS upload; use `result.ass`, not expanded `new.ass`. |
| `moegirl_wikitext` | Full pasted Wikitext, preserving `LyricsKai/colors`, `charas`, `colors`, `original`, and singer tags such as `@1`. |
| `moegirl_url` | Alternative lyric-page URL. Leave empty when using pasted Wikitext: a nonempty URL takes precedence. |
| `title` | Optional explicit song title. |
| `enable_furigana` | Default `false`. Keep false for existing JPKara/YOHANE readings when only applying singer assignments or metadata. |
| `furigana_existing_mode` | Used when annotation is enabled: `skip` skips an entire line with existing readings; `clear` clears and reannotates (service default). |
| `include_project_garbage` | Set `true` to add the Aegisub project metadata section. |
| `video_file` | Usually `input.mp4`; sets both `Audio File` and `Video File`. No video upload is needed. |
| `color_map_json` | Optional JSON object encoded as a form string, mapping exact character names to colors, e.g. `{"角色A":"#FF0000"}`. Supports RGB/ASS BGR forms. |
| `all_mode` | Default `scraped`; `mixed` expands group singing into member assignments. The web UI also offers `custom` with an explicit `all` entry in `color_map_json`. |
| `actor_color_groups` | Optional JSON array encoded as a string, e.g. `[{"members":["角色A","角色B"],"color":"#00AACC"}]`; replaces matching member groups with generated `color-N` actors and color entries. |
| `split_harmony` | Default `false`. Extracts half-width parenthesized lyric content into `harmony_ass`; this is subtitle splitting, not audio stem separation. |
| `harmony_gap_fill` / `harmony_gap_threshold_s` | Optional harmony placeholder filling; defaults `false` / `10`. |
| `enable_katakana_english` | Optional katakana-to-English annotation, default `false`. Related fields: `katakana_reverse_mode=false`, `katakana_min_len=5`. |

Furigana source priority is Moegirl ruby data → LLM → Kakasi. Enabling annotation can redistribute K values across reading syllables. Use it only when readings should be added/rebuilt; `skip` is not equivalent to preserving every existing K tag while filling partial readings on the same line.

## Example: aligned ASS + Wikitext + video metadata

From the song directory, with UTF-8 `lyrics.wiki` and `result.ass`:

```bash
curl --fail-with-body -sS --max-time 180 https://aegi.umi-cv.com/api/process \
  -F 'file=@result.ass' \
  -F 'moegirl_wikitext=<lyrics.wiki' \
  -F 'enable_furigana=false' \
  -F 'split_harmony=false' \
  -F 'include_project_garbage=true' \
  -F 'video_file=input.mp4' \
  -o aegi.response.json
```

Check HTTP success before extracting `ass` from the JSON. Save it to a staging file such as `result.processed.ass` and validate before replacing `result.ass` with a backup. Do not save the entire JSON response with an `.ass` extension. If requested, save nonempty `harmony_ass` as `result_har.ass`; its response field name does not change our filename convention.

Successful responses contain `ass`, `harmony_ass`, `line_count`, `color_count`, `chara_count`, `color_map`, `scraped_color_map`, `moegirl_debug`, and `logs`. Errors can include `detail` plus logs/debug data. Review `logs` for `ass event unmatched` even when HTTP status is 200; a successful request alone does not prove every singer assignment matched.

## Placement in the KTV workflow and checks

1. Supply the aligned, reading-corrected source ASS. Without an ASS file, the service can generate zero-timed lyrics from Wikitext; that does not perform audio alignment.
2. Apply requested actor/color/metadata processing. With furigana and harmony splitting disabled, check lyric event start/end times, K values, visible lyrics, and readings against the input; actor names and inline singer markers may change.
3. Reapply/verify the desired styles, font sizes, title lines, and colors. The service rebuilds its own header and KTV template comments, and emits lyric events with `Style=Default`; it does not preserve arbitrary input styles or existing expanded effects. In the synthetic live check, K1/K2 font size was 120, not the user's earlier 108-size setting.
4. For metadata, verify `[Aegisub Project Garbage]` points to the correct relative video filename. The generated section also includes aspect ratio, zoom, scroll/active-line, and video-position values.
5. Keep the validated source as `result.ass` / `result_har.ass`, then run `aegisub_cli_template.py` to obtain `new.ass` / `new_har.ass`.

The live two-line synthetic test correctly assigned two singers while preserving event times, K tags, and existing `|<` / `#|<` readings with `enable_furigana=false`. Larger songs still require unmatched-line and timing checks, especially if the Wikitext and ASS use different line breaks.
