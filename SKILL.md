---
name: jpkara-ktv
description: Download, generate, edit, and render Japanese KTV media with jpkara/yohane and FFmpeg, including ASS styling, karaoke timing, GPU encoding, and audio-track muxing.
---

# JPKara KTV

Use this skill for Japanese song KTV work: obtaining source media, generating or editing timed ASS subtitles, and rendering verified on-vocal/off-vocal videos.

Read only the reference needed for the current operation:

- Setup and forced alignment: [references/setup-and-alignment.md](references/setup-and-alignment.md)
- Lyrics lookup and cleanup: [references/lyrics-sources.md](references/lyrics-sources.md)
- ASS styles, speakers, and `color_table`: [references/ass-style-and-speakers.md](references/ass-style-and-speakers.md)
- Bilibili DASH download: [references/bilibili-download.md](references/bilibili-download.md)
- Rendering, audio muxing, verification, and exact clipping: [references/render-and-verify.md](references/render-and-verify.md)

## Reusable workflow scripts

Reusable helpers live in [scripts/](scripts/):

- `split_lyrics.py`: split overlong lines (default 15 characters) without cutting an ASCII word.
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
- `render_on_off.py`: burn an ASS video once, then mux a verified original/full-mix ON VOCAL version and an Instrumental OFF VOCAL version without encoding the subtitle video twice.
- `aegisub_cli_template.py`: run Aegisub CLI's K1/K2 interleave macro followed by Apply karaoke template; save the fully expanded effect ASS with the standard name.
- `bilibili_metadata.py`: fetch a Bilibili BV URL's title, description, tags, owner, pages, dimensions, durations, statistics, rights, and non-expiring stream summaries into a JSON sidecar.
- `bilibili_submit.py`: dry-run or submit verified ON/OFF videos as one Bilibili archive using `source_metadata.json`; supports UPOS chunk upload, local Cookie credentials, and QR login.

The splitter is deterministic but needs a manual phrasing review. YOHANE reading generation and FA-Kara alignment remain separate: FA-Kara does not provide readings.

## Alignment engine choice (mandatory)

Before invoking any alignment engine, ask the user which one to use for this run:

- `jpkara/yohane`: can perform reading/furigana analysis and forced alignment. Use it for a complete lyrics → annotated/aligned ASS workflow.
- `FA-Kara` (`~/FA-Kara`, commonly installed as `/home/birchtree/FA-Kara`; repository: [moriwx/FA-Kara](https://github.com/moriwx/FA-Kara)): alignment only. It does **not** provide a reading/furigana service. Supply already annotated lyrics in FA-Kara's `{surface|reading}` format plus vocals-only audio; it produces its own karaoke ASS timing. Do not call FA-Kara expecting it to generate or correct readings.

Ask this even when the user requests a rerun; if the user explicitly names an engine in the current request, confirm that choice before running it. If FA-Kara is selected, read the FA-Kara section in [references/setup-and-alignment.md](references/setup-and-alignment.md) and keep reading generation separate.

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
3. Ask the user to choose the alignment engine (`jpkara/yohane` or `FA-Kara`) before running alignment. If `jpkara/yohane` is missing, follow the portable clone/setup/validation flow in the setup reference; do not silently skip forced alignment. If FA-Kara is selected, verify its checkout and dependencies instead.
4. Obtain UTF-8 lyrics, one sung line per line, using the lyrics reference. Do not reproduce full copyrighted lyrics in the response.
5. Generate or align ASS with the selected engine, preserving `Name`/Actor fields when present. For FA-Kara, convert existing annotated ASS text into its required reading format and run alignment only; do not rerun or delegate reading analysis to FA-Kara.
6. Apply requested ASS style, title, color, and speaker mappings using the ASS reference.
7. Save the aligned, reading-annotated source as `result.ass`; if backing/harmony vocals are aligned separately, save those as `result_har.ass`. Run the Aegisub CLI template section below to produce `new.ass` and, when applicable, `new_har.ass` before video rendering. Do not overwrite a source ASS with its expanded template output.
8. Create or replace lyric-cover visuals with `make_cover_video.py` when requested; label removal or artwork repair is an upstream image-editing step, not an FFmpeg crop/blur operation.
9. Render or remux using the rendering reference. Prefer `render_on_off.py` for paired outputs, then verify streams, duration, audio intent, and ON-audio packet identity.

## 用 Aegisub CLI 生成并保存 KTV 模板特效

Use [scripts/aegisub_cli_template.py](scripts/aegisub_cli_template.py) after timing, readings, style, and speaker edits are complete. It runs Karaoke Helper's **转换为双层交错形式** (K1/K2) and then Aegisub's **Apply karaoke template**, saving the expanded ASS. This is ASS effect generation; burning it into MP4 is a later FFmpeg step. Input/output names are fixed by convention: `result.ass` → `new.ass`, and separate backing/harmony vocals `result_har.ass` → `new_har.ass`. Do not treat a `new*.ass` as the source for another template run.

The script needs [Myaamori/aegisub-cli](https://github.com/Myaamori/aegisub-cli), the user's `karaoke-helper.lua`, and Aegisub's `kara-templater.lua`. It makes a temporary ASCII-name copy of the helper containing only an ASCII CLI alias for the second macro; the user's original Lua is unchanged. It also stages Chinese-named ASS paths and leaves the Unicode countdown glyph at the Lua default, avoiding observed Windows CLI encoding failures. It refuses to replace an existing output unless `--overwrite` is given. Read [references/render-and-verify.md](references/render-and-verify.md#aegisub-cli-template-expansion) for the exact command and validation.

## Bilibili submission conventions

For this user's newly produced KTV submissions, default to original/self-made (`copyright=1`) unless the user chooses otherwise. Match the logged-in uploader's established KTV title style. For paired ON/OFF posts, use `【ニコカラ/ktv字幕】{曲名} - {演唱者}{作品标签}（On/Off Vocal）【纯K自用】`; `作品标签` is optional when not reliably established. For example, `百色リメイン` uses `【ニコカラ/ktv字幕】百色リメイン - スタァライト九九組【少女歌剧】（On/Off Vocal）【纯K自用】`. Check the logged-in account's recent KTV submissions before publishing; use the example for formatting, never as another song's identity. The prefix, song and artist, voice marker, and exactly one final `【纯K自用】` must survive the 80-character limit. Shorten deliberately or ask the user; never silently truncate. This is a future-submission convention, not authorization to rename existing published archives.

Use the fixed `scripts/bilibili_submit.py` submission path, not a one-off uploader, for new posts. Give it an explicit `--title` or `publication_title` in the metadata; the source video's `title` and `description` are not publication copy. For paired posts pass the rendered ON file with `--video` and the rendered OFF file with `--off-video`; the script makes one archive with parts `on vocal` and `off vocal`. Run without `--submit` first and review the full payload (title, song/artist, part order, description/credits, source URL, tags, cover, copyright, and privacy). Then use `--submit` only when publication is authorized. A single-part post may use `（On Vocal）` or `（Off Vocal）` instead. If account style has changed or the performer/series is uncertain, resolve that before posting.

For authorized submissions, include separate description lines: `片源：<source URL>`, `字幕：<user-selected alignment engine>` (for example `字幕：FA-KARA` or `字幕：YOHANE`), and `分词：萌娘百科` when that is the actual character/lyric split source. Preserve another source if the user chose one; do not invent attribution when no split source was used. Record these as `subtitle_engine` and `lyrics_split_source` in the song metadata, or pass `--subtitle-engine` and `--lyrics-split-source` to `bilibili_submit.py`. FA-KARA credit identifies alignment, not reading generation.

Use lowercase Bilibili part titles `on vocal` and `off vocal`, including when constructing multipart payloads. These are publication titles; local media filenames do not need renaming. Select tags using search results about the actual song/performers/project, remove unrelated platform campaign tags, and keep at most 10; the script rejects longer lists instead of silently dropping tags. Retain the source URL even for an original/self-made submission. Submit the verified subtitle-rendered media, not the unrendered `input.mp4`.

When authorized to replace an OFF part, reuse the existing archive and ON part, upload only the corrected OFF video, and verify the returned part filenames/CIDs, credits, lowercase titles, and copyright type. Persist upload identifiers for retries. Use the server-provided UPOS filename stem rather than the local filename. The archive-view response is not directly an edit payload: convert `recreate` objects to their integer `switch` value and subtitle settings to `{open, lan}`. Do not resubmit an archive after a successful response; read back its state. Keep any requested title-only exception for an existing archive.

## 视频下载

### YouTube

Use `yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mp4`, then verify the local MP4 with `ffprobe`. Do not use an ad-hoc downloader or expose cookies/tokens in logs.

### Bilibili

Download DASH video and audio separately, save them completely, and merge offline with FFmpeg. Do not real-time mix, use top-level quality as proof of 1080P, or silently downgrade a missing `id == 80` track. Follow [references/bilibili-download.md](references/bilibili-download.md).

### m3u8 stream

Use FFmpeg for VOD HLS/m3u8 remuxing, preserving only required headers. Verify the resulting MP4. For live streams, require a bounded recording or an ended stream before claiming completion.

## 视频处理

### 视频截取 `t1`–`t2`

Use input-side `-ss` before `-i` for fast keyframe seeking, then output-side `-ss` after `-i` to decode from the nearby point to the exact boundary. Use `-t t2-t1`; absolute accuracy requires re-encoding and cannot be guaranteed with pure `-c copy`. See [references/render-and-verify.md](references/render-and-verify.md).

## ASS 与渲染

For styles, Aegisub syntax, `Name`/Actor, `color_table`, MyGO colors, GPU rendering, audio muxing, and final validation, read the relevant sections in the linked references rather than duplicating their long procedures here.  [references/ass-style-and-speakers.md](references/ass-style-and-speakers.md)
