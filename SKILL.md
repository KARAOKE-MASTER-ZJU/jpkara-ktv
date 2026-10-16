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

If a video already has the correct burned-in subtitles but the wrong audio, mux the correct audio with `-c:v copy` instead of re-encoding the video. Use a temporary output and replace the target only after validation succeeds.

## Workflow

1. Inspect available files, streams, durations, subtitle tracks, and GPU encoders.
2. If source media comes from a platform, use the matching download section below and verify it before alignment.
3. Ask the user to choose the alignment engine (`jpkara/yohane` or `FA-Kara`) before running alignment. If `jpkara/yohane` is missing, follow the portable clone/setup/validation flow in the setup reference; do not silently skip forced alignment. If FA-Kara is selected, verify its checkout and dependencies instead.
4. Obtain UTF-8 lyrics, one sung line per line, using the lyrics reference. Do not reproduce full copyrighted lyrics in the response.
5. Generate or align ASS with the selected engine, preserving `Name`/Actor fields when present. For FA-Kara, convert existing annotated ASS text into its required reading format and run alignment only; do not rerun or delegate reading analysis to FA-Kara.
6. Apply requested ASS style, title, color, and speaker mappings using the ASS reference.
7. Create or replace lyric-cover visuals with `make_cover_video.py` when requested; label removal or artwork repair is an upstream image-editing step, not an FFmpeg crop/blur operation.
8. Render or remux using the rendering reference. Prefer `render_on_off.py` for paired outputs, then verify streams, duration, audio intent, and ON-audio packet identity.

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
