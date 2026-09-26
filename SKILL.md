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

## Critical audio invariant

Inspect all media before rendering and distinguish the tracks:

- `on-vocal` means the complete original mix, normally the audio stream in the source video or a supplied full-mix file. Never use an isolated `Vocals` stem as the finished on-vocal soundtrack.
- `off-vocal` means the instrumental/karaoke stem, normally named `Instrumental`.
- `Vocals` is useful for forced alignment, not for the finished on-vocal audio.

If a video already has the correct burned-in subtitles but the wrong audio, mux the correct audio with `-c:v copy` instead of re-encoding the video. Use a temporary output and replace the target only after validation succeeds.

## Workflow

1. Inspect available files, streams, durations, subtitle tracks, and GPU encoders.
2. If source media comes from a platform, use the matching download section below and verify it before alignment.
3. If jpkara/yohane is missing, follow the portable clone/setup/validation flow in the setup reference; do not silently skip forced alignment.
4. Obtain UTF-8 lyrics, one sung line per line, using the lyrics reference. Do not reproduce full copyrighted lyrics in the response.
5. Generate or align ASS with jpkara, preserving `Name`/Actor fields when present.
6. Apply requested ASS style, title, color, and speaker mappings using the ASS reference.
7. Render or remux using the rendering reference, then verify streams, duration, and audio intent.

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
