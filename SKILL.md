---
name: jpkara-ktv
description: Download, generate, edit, and render Japanese KTV media with jpkara/yohane and FFmpeg, including ASS styling, karaoke timing, GPU encoding, and audio-track muxing.
---

# JPKara KTV

Use this skill for Japanese song KTV work: obtaining source media, generating or editing timed ASS subtitles, and rendering verified on-vocal/off-vocal videos.

Read only the reference needed for the current operation:

- Existing UVR models, setup, and forced alignment: [references/setup-and-alignment.md](references/setup-and-alignment.md)
- Lyrics lookup and cleanup: [references/lyrics-sources.md](references/lyrics-sources.md)
- ASS styles, speakers, and `color_table`: [references/ass-style-and-speakers.md](references/ass-style-and-speakers.md)
- Remote Wikitext speaker assignment, furigana, and Aegisub video metadata: [references/aegi-api.md](references/aegi-api.md)
- Bilibili DASH download: [references/bilibili-download.md](references/bilibili-download.md)
- Rendering, audio muxing, verification, and exact clipping: [references/render-and-verify.md](references/render-and-verify.md)

## Reusable workflow scripts

Reusable helpers live in [scripts/](scripts/):

Use these helpers before writing shell pipelines or per-song Python. Set `KTV_SKILL_DIR` to the discovered skill directory and invoke its scripts from the song directory. Read only the selected command's `--help`; open implementation or protocol references when a missing feature or failure requires it. Add recurring missing operations to these maintained helpers with behavior checks instead of creating another disposable wrapper. Do not make a new per-song `build.py`, `download.py`, `replace.py`, or verification script for an operation already covered below.

Rendering prints concise stages/errors and saves detailed verification to JSON. Template expansion hides successful automation logs (`--verbose` restores them). Read report fields needed for the next decision rather than dumping full probes, frame progress, scripts, or all reference documents into context.

- `split_lyrics.py`: split overlong lines (default 15 characters) without cutting an ASCII word.
- `moegirl_wikitext.py`: export full-page Wikitext through a native Linux Playwright browser with a private persistent login profile; see the lyrics reference for setup and manual login.
- `yohane_readings_to_fa.py`: generate FA-Kara `{surface|reading}` text with jpkara/YOHANE.
- `ass_to_fa_lyrics.py`: convert existing jpkara ASS reading tags to FA-Kara input without rerunning reading analysis.
- `run_fa_kara.py`: run FA-Kara on vocals-only audio and copy native `o.ass` to a named output; CPU is the safe default.
- `apply_speakers.py`: copy a reference ASS style/color table and apply a supplied song's character split to aligned dialogue events.
- `scale_ass_styles.py`: scale ASS style geometry from one base font size to another while preserving timing and colors.
- `flatten_furigana_ass.py`: remove `|<`/`#|` furigana groups, merge their karaoke durations into the surface word, and trim empty edge syllables without changing their absolute timing.
- `normalize_furigana_ass.py`: convert FA-Kara bare continuation readings (`#|reading`) to the Aegisub/jpkara furigana form (`#|<reading`) without changing timing or deleting readings.
- `fix_okurigana_ass.py`: split mixed kanji/okurigana words after FA-Kara so ruby stays above kanji only (for example, `終|<お` followed by plain `わって`).
- `normalize_fa_lyrics.py`: repair existing FA-Kara input so mixed words use kanji-only readings (`{終|お}わって`, `{見|み}つけ{出|だ}して`) before alignment.
- `make_cover_video.py`: create a 1920×1080 lyric/album-cover video with an enlarged blurred background, a smaller sharp square cover, adjustable top clearance, and bit-identical AAC copied from a source video.
- `fix_countdown_spacing.py`: repair source ASS countdown spacing above K1 ruby, preserve timing, and refuse expanded effects; supports dry-run and configurable gap.
- `render_on_off.py`: `--mode on|off|both`, optional `--harmony-ass`, explicit output dimensions/quality, AAC copy or one-pass conversion, full/tail verification, and automatic JSON report. Burn the subtitle video only once.
- `aegisub_cli_template.py`: expand K1/K2 and karaoke templates; `--fix-countdown` repairs source spacing before expansion, avoiding a separate editing script.
- `bilibili_download.py`: download actual 1080P DASH tracks concurrently, retry safely, save actual-track metadata, merge offline, validate duration, and clean download intermediates after success.
- `bilibili_metadata.py`: fetch a Bilibili BV URL's title, description, tags, owner, pages, dimensions, durations, statistics, rights, and non-expiring stream summaries into a JSON sidecar.
- `bilibili_submit.py`: dry-run/submit ON/OFF; `--aid ... --replace-part on|off` edits an existing archive while preserving other parts, saves retry receipts, and reads back status. No separate uploader/editor wrapper is needed.

The splitter is deterministic but needs a manual phrasing review. YOHANE reading generation and FA-Kara alignment remain separate: FA-Kara does not provide readings.

## Alignment engine choice (mandatory)

Before the first alignment run, establish the user's engine choice; ask if neither the current request nor the ongoing task already specifies one:

- `jpkara/yohane`: can perform reading/furigana analysis and forced alignment. Use it for a complete lyrics → annotated/aligned ASS workflow.
- `FA-Kara` (repository: [moriwx/FA-Kara](https://github.com/moriwx/FA-Kara)): alignment only. It does **not** provide a reading/furigana service. Supply already annotated lyrics in FA-Kara's `{surface|reading}` format plus vocals-only audio; it produces its own karaoke ASS timing. Do not call FA-Kara expecting it to generate or correct readings.

An explicit engine choice in the current task is sufficient; carry it through continuations and retries. Ask only when the choice is missing or the user requests a change. Reusing an existing ASS for styling, rendering, or a verified replacement source does not require another alignment run or engine question. If FA-Kara is selected, read the FA-Kara section in [references/setup-and-alignment.md](references/setup-and-alignment.md) and keep reading generation separate.

## Resource and source preferences

If UVR is installed, inspect its existing weights and companion model metadata first, including user-mentioned drives and Windows installations when running under WSL. Prefer a compatible installed model; do not download a duplicate merely because a Python separator uses a different cache directory. See the setup reference for staging and cleanup.

For this user's workflow, prefer a complete, matching Bilibili video when available, unless the user explicitly chooses another source. YouTube-derived media may encounter Bilibili transcoding compatibility problems; this is a fallback consideration, not proof that YouTube is the cause of any particular failure. Verify the actual version, quality, and duration, retain original MV attribution when known, and check synchronization before reusing an ASS with another source.

## Critical audio invariant

Inspect all media before rendering and distinguish the tracks:

- `on-vocal` means the complete original mix, normally the audio stream in the source video or a supplied full-mix file. Never use an isolated `Vocals` stem as the finished on-vocal soundtrack.
- `off-vocal` means the instrumental/karaoke stem, normally named `Instrumental`.
- `Vocals` is useful for forced alignment, not for the finished on-vocal audio.

Preserve both model-produced vocals and instrumental stems and record the model filename and source time range. Before OFF rendering, check vocal suppression on sung passages and verify that the stem and video share the same time origin. Do not apply the initial trim again to stems extracted from an already-trimmed video. Do not treat `amix weights='1 -1'` as verified subtraction: the local FFmpeg produced addition in this workflow. Prefer the model's instrumental output; any residual reconstruction needs a numerical subtraction check and matching gains/timing before use. Container/codec validation alone does not establish that an OFF soundtrack is correct.

If a video already has the correct burned-in subtitles but the wrong audio, mux the correct audio with `-c:v copy` instead of re-encoding the video. Use a temporary output and replace the target only after validation succeeds.

## Workflow

1. Inspect available files, streams, durations, subtitle tracks, and GPU encoders.
2. If source media comes from a platform, use the matching download section below and verify it before alignment.
   For every Bilibili source, run `bilibili_metadata.py` immediately after resolving the BV id and keep the JSON sidecar beside the downloaded media as `source_metadata.json` (the existing KTV convention). Its compact schema intentionally omits uploader, bitrate, and page-list fields unless the user asks for them. Keep the `tags` array at no more than 10 entries, selecting source/search-supported tags. If the description provides an original source URL, preserve it as `source_material_url`; do not invent one from a bare note such as `片源: ytb`. Never store signed DASH `base_url` values in the sidecar because they expire.
3. Confirm the alignment engine (`jpkara/yohane` or `FA-Kara`) from the user's instructions, asking only if the choice is missing. If `jpkara/yohane` is missing, follow the portable clone/setup/validation flow in the setup reference; do not silently skip forced alignment. If FA-Kara is selected, verify its checkout and dependencies instead.
4. Obtain UTF-8 lyrics, one sung line per line, using the lyrics reference. Do not reproduce full copyrighted lyrics in the response.
5. Generate or align ASS with the selected engine, preserving `Name`/Actor fields when present. For FA-Kara, convert existing annotated ASS text into its required reading format and run alignment only; do not rerun or delegate reading analysis to FA-Kara.
6. Apply requested ASS style, title, color, and speaker mappings using the ASS reference. For the `aegi.umi-cv.com` service, follow the API reference below; run it before final style adjustments because it rebuilds the ASS header and styles.
7. Save the aligned, reading-annotated source as `result.ass`; if backing/harmony vocals are aligned separately, save those as `result_har.ass`. Run the Aegisub CLI template section below to produce `new.ass` and, when applicable, `new_har.ass` before video rendering. Do not overwrite a source ASS with its expanded template output.
8. Create or replace lyric-cover visuals with `make_cover_video.py` when requested; label removal or artwork repair is an upstream image-editing step, not an FFmpeg crop/blur operation.
9. Render or remux using the rendering reference. Prefer `render_on_off.py` for paired outputs, then verify streams, duration, audio intent, and ON-audio packet identity.

## 萌娘百科分词与 ASS 处理 API

获取萌娘百科 Wikitext 时：如果是 GPT 桌面版，直接使用 Computer Use 操作浏览器；如果是命令行环境，使用 Playwright（`scripts/moegirl_wikitext.py`）。若当前环境未提供 Computer Use，应明确说明，不要假定可以调用；两种方式都只读取源码，不提交编辑。

The [Aegisub ASS Tool](https://aegi.umi-cv.com/) ([source repository](https://github.com/KARAOKE-MASTER-ZJU/subtitle-moegirl-itool)) accepts aligned ASS plus Moegirl Wikitext to assign singers and colors, optionally annotate furigana, and add `[Aegisub Project Garbage]` pointing to the song video. Read [references/aegi-api.md](references/aegi-api.md) before calling its `POST /api/process` endpoint. For already annotated/aligned lyrics, use `enable_furigana=false` to retain the existing readings. This service rebuilds styles/templates and normalizes lyric styles to `Default`; use it after alignment and before final style edits and Aegisub CLI template expansion. It returns source ASS content for `result.ass` / `result_har.ass`, not the fully expanded `new.ass` / `new_har.ass`. Keep the input until output timing, readings, actor assignments, and styles have been checked.

## 用 Aegisub CLI 生成并保存 KTV 模板特效

Use [scripts/aegisub_cli_template.py](scripts/aegisub_cli_template.py) after timing, readings, style, and speaker edits are complete. It runs Karaoke Helper's **转换为双层交错形式** (K1/K2) and then Aegisub's **Apply karaoke template**, saving the expanded ASS. This is ASS effect generation; burning it into MP4 is a later FFmpeg step. Input/output names are fixed by convention: `result.ass` → `new.ass`, and separate backing/harmony vocals `result_har.ass` → `new_har.ass`. Do not treat a `new*.ass` as the source for another template run.

The skill bundles a snapshot of 46 Aegisub automation `.lua` files in [assets/aegisub-automation/](assets/aegisub-automation/), preserving their relative paths. Invoke `python "$KTV_SKILL_DIR/scripts/aegisub_cli_template.py" result.ass` from the song directory, where `KTV_SKILL_DIR` is the skill's discovered installation directory. The Aegisub CLI executable is not bundled; supply `--cli`, set `AEGISUB_CLI`, or put it on PATH. The wrapper makes a temporary ASCII-name copy of the helper containing an ASCII CLI alias for the second macro; the bundled Lua is unchanged. It stages Chinese-named ASS paths and leaves the Unicode countdown glyph at the Lua default, avoiding observed Windows CLI encoding failures. It refuses to replace existing output unless `--overwrite` is given. For sources, setup, and validation read [references/render-and-verify.md](references/render-and-verify.md#aegisub-cli-template-expansion).

## Bilibili submission conventions

For this user's newly produced KTV submissions, default to original/self-made (`copyright=1`) unless the user chooses otherwise. Match the logged-in uploader's established KTV title style. For paired ON/OFF posts, use `【ニコカラ/ktv字幕】{曲名} - {演唱者}{作品标签}（On/Off Vocal）【纯K自用】`; `作品标签` is optional when not reliably established. For example, `百色リメイン` uses `【ニコカラ/ktv字幕】百色リメイン - スタァライト九九組【少女歌剧】（On/Off Vocal）【纯K自用】`. Check the logged-in account's recent KTV submissions before publishing; use the example for formatting, never as another song's identity. The prefix, song and artist, voice marker, and exactly one final `【纯K自用】` must survive the 80-character limit. Shorten deliberately or ask the user; never silently truncate. This is a future-submission convention, not authorization to rename existing published archives.

Use the fixed `scripts/bilibili_submit.py` submission path, not a one-off uploader, for new posts. Give it an explicit `--title` or `publication_title` in the metadata; the source video's `title` and `description` are not publication copy. For paired posts pass the rendered ON file with `--video` and the rendered OFF file with `--off-video`; the script makes one archive with parts `on vocal` and `off vocal`. Run without `--submit` first and review the full payload (title, song/artist, part order, description/credits, source URL, tags, cover, copyright, and privacy). Then use `--submit` only when publication is authorized. A single-part post may use `（On Vocal）` or `（Off Vocal）` instead. If account style has changed or the performer/series is uncertain, resolve that before posting.

For authorized submissions, include separate description lines: `片源：<source URL>`, `字幕：<user-selected alignment engine>` (for example `字幕：FA-KARA` or `字幕：YOHANE`), and `分词：萌娘百科` when that is the actual character/lyric split source. Preserve another source if the user chose one; do not invent attribution when no split source was used. Record these as `subtitle_engine` and `lyrics_split_source` in the song metadata, or pass `--subtitle-engine` and `--lyrics-split-source` to `bilibili_submit.py`. FA-KARA credit identifies alignment, not reading generation.

Use lowercase Bilibili part titles `on vocal` and `off vocal`, including when constructing multipart payloads. These are publication titles; local media filenames do not need renaming. Select tags using search results about the actual song/performers/project, remove unrelated platform campaign tags, and keep at most 10; the script rejects longer lists instead of silently dropping tags. Retain the source URL even for an original/self-made submission. Submit the verified subtitle-rendered media, not the unrendered `input.mp4`.

When authorized to replace an ON or OFF part, read the current archive first, retain unaffected parts and their CIDs, and upload only the corrected part. A user may have removed or renamed parts since the last attempt; do not replay stale archive data. Verify returned part filenames/CIDs, part order, credits, lowercase titles, and copyright type. Preserve current cover and unrelated user edits. Persist upload identifiers for retries. Use the server-provided UPOS filename stem rather than the local filename. The archive-view response is not directly an edit payload: convert `recreate` objects to their integer `switch` value and subtitle settings to `{open, lan}`. Do not resubmit after a successful response; read back its state. Report upload/submission acceptance, transcoding completion, and review/publication as separate states. A successful edit response or successful OFF part does not establish that ON transcoding passed. Keep any requested title-only exception for an existing archive.

Use `bilibili_submit.py source_metadata.json --video song_ON_VOCAL.mp4 --aid ARCHIVE_AID --replace-part on` for the read-only edit preview, then the same command with `--submit` when authorized. Edit preview needs authenticated archive lookup; it does not upload. Existing metadata is preserved unless explicitly overridden; `--update-source` updates the source-credit line. If adding ON back to an OFF-only archive, explicitly supply the reviewed paired `--title` when appropriate. Reuse the saved receipt on a retry of the same file; use another `--receipt` for a genuinely new replacement file. An uncertain prior POST stops automatic retry.

After validated replacement, clean only temporary files and failed downloads owned by this task. Preserve installed UVR weights, both stems, reusable ASS, final media, source attribution, and upload receipts. Never publish session-specific absolute paths, drive layouts, cookies, signed media URLs, or production traces in this skill; use configurable variables and generic examples.

## 视频下载

### YouTube

Use `yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mp4`, then verify the local MP4 with `ffprobe`. Do not use an ad-hoc downloader or expose cookies/tokens in logs.

### Bilibili

Run `python "$KTV_SKILL_DIR/scripts/bilibili_download.py" VIDEO_URL --output input.mp4`; URL `p=` or `--page` selects a part. The helper saves the source metadata automatically. Do not write another downloader. See [references/bilibili-download.md](references/bilibili-download.md) only for protocol details or troubleshooting; do not silently downgrade a missing `id == 80` track.

### m3u8 stream

Use FFmpeg for VOD HLS/m3u8 remuxing, preserving only required headers. Verify the resulting MP4. For live streams, require a bounded recording or an ended stream before claiming completion.

## 视频处理

### 视频截取 `t1`–`t2`

Use input-side `-ss` before `-i` for fast keyframe seeking, then output-side `-ss` after `-i` to decode from the nearby point to the exact boundary. Use `-t t2-t1`; absolute accuracy requires re-encoding and cannot be guaranteed with pure `-c copy`. See [references/render-and-verify.md](references/render-and-verify.md).

## ASS 与渲染

For styles, Aegisub syntax, `Name`/Actor, `color_table`, MyGO colors, GPU rendering, audio muxing, and final validation, read the relevant sections in the linked references rather than duplicating their long procedures here.  [references/ass-style-and-speakers.md](references/ass-style-and-speakers.md)
