# Rendering and verification

Read this reference when burning ASS subtitles or producing on-vocal/off-vocal MP4 files.

## Aegisub CLI template expansion

Before burning subtitles into video, expand the ASS template. From the song directory, with `result.ass` present and `KTV_SKILL_DIR` set to the discovered skill directory:

```bash
python "$KTV_SKILL_DIR/scripts/aegisub_cli_template.py" result.ass
```

This writes `new.ass`; pass `result_har.ass` to write `new_har.ass`. Keep those names even when the alignment engine changes. To replace a previously generated `new.ass` after reviewing it, add `--overwrite`. The script runs the GUI-equivalent default K1/K2 settings (`Default`, 2000 ms advance, 1000 ms extension, 4000 ms section gap, countdown enabled), then **Apply karaoke template**. It stages files under the CLI directory by default; use `--scratch-parent` if that directory is not writable. The scratch path must be ASCII-only and accessible to the Windows executable.

The skill includes a byte-for-byte snapshot of the 46 `.lua` files under this machine's Aegisub `automation/` directory at `assets/aegisub-automation/`, including `autoload/karaoke-helper.lua` and `autoload/kara-templater.lua`. It does not include MoonScript (`.moon`) files or an Aegisub executable. The Lua sources are associated with [Sonata1015/aegisub-karaoke-helper](https://github.com/Sonata1015/aegisub-karaoke-helper) and [TypesettingTools/Aegisub](https://github.com/TypesettingTools/Aegisub); the CLI is [Myaamori/aegisub-cli](https://github.com/Myaamori/aegisub-cli). These links identify upstream projects, not a claim that every local file is identical to the latest upstream version. Install the CLI beside Aegisub; on another machine pass `--cli /path/to/aegisub-cli.exe` or set `AEGISUB_CLI`. `--helper` and `--templater` can override the bundled Lua files.

Confirm the generated ASS has K1/K2 source comments and expanded `fx` Dialogue rows, preserves lyrics and timing, and has no template Lua errors. The script checks that the generated Dialogue count increased; inspect title lines and a few visual frames separately. On the tested `3·7·5·1·0` sample, its 5599 non-Title effect rows matched Aegisub GUI `new.ass` exactly. This operation produces an ASS file, not a video.

## Lyric/album-cover video

Use `scripts/make_cover_video.py` for a static 16:9 cover video. It accepts either a clean cover image or a crop from a source-video frame, fills the canvas with an enlarged blurred copy, overlays a smaller sharp square, encodes a one-second H.264 loop, and repeats that loop by stream copy. The source video's first AAC stream is copied without re-encoding and verified by packet MD5.

For the proven 1920×1080 layout with extra room above the cover for top lyrics and furigana:

```bash
python scripts/make_cover_video.py \
  --source-video input.mp4 --crop 660:240:600 \
  --cover-size 500 --cover-y 330 --blur-sigma 12 \
  --output input_cover_replaced.mp4
```

The crop is song-specific; inspect a frame before choosing it. `--blur-sigma`, `--cover-size`, and `--cover-y` are adjustable. If a label or watermark must be removed, first create or supply a clean `--cover-image`; the script deliberately performs no generative removal and makes no copyright-status claim.

## Paired ON/OFF rendering

Use `scripts/render_on_off.py` when both versions are needed. It burns the ASS into the video once, copies the original/full-mix AAC packet-for-packet into ON VOCAL, encodes the Instrumental to stereo AAC for OFF VOCAL, validates both files, and decodes their final second. Never pass a `Vocals` stem as `--full-mix`.

```bash
python scripts/render_on_off.py \
  --video input_cover_replaced.mp4 --ass NEW2.ass \
  --instrumental '1_input_(Instrumental).wav' \
  --output-prefix 'song' --preview-png preview.png
```

Normally inspect a preview when layout or fonts changed. If the user requested no preview, omit `--preview-png` and use the spacing checks in the ASS reference; do not add a preview approval gate. The script defaults `--full-mix` to `--video`, uses NVENC when available with a libx264 fallback, and refuses to overwrite existing outputs unless `--overwrite` is supplied.

## Burn subtitles with NVENC

If an isolated vocals stem is used only as a temporary base, do not label that file `on_vocal`; mux the full mix afterward:

```bash
ffmpeg -y -i input.mp4 -i "1_input_(Vocals).mp3" \
  -map 0:v:0 -map 1:a:0 -vf 'subtitles=new.ass' \
  -c:v h264_nvenc -preset p5 -tune hq -rc:v vbr -cq:v 19 -b:v 0 \
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -shortest -movflags +faststart subtitle_video.mp4
```

For the finished on-vocal file, use the source video's original/full-mix audio:

```bash
ffmpeg -y -i rendered_video.mp4 -i input.mp4 \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy \
  -shortest -movflags +faststart on_vocal.mp4
```

For off-vocal, map the instrumental stem. If both outputs share burned-in video, render once and mux two audio tracks rather than encoding video twice.

## Verify

For every final MP4, use `ffprobe` to confirm one H.264 video stream, one AAC stereo audio stream, matching duration, and the intended audio source. Write temporary outputs and replace targets only after validation. Report whether the video was encoded or only remuxed.

## Reuse ASS with a replacement source

Confirm the same song version, edit, frame rate, full duration, and start/end content before rendering. Compare decoded audio at the beginning, middle, and end, using normalized correlation when appropriate. A constant offset can be applied once to the ASS; varying offsets indicate an edit or speed difference and require local repair. A difference below the ASS timing resolution generally does not justify a whole-song realignment. Keep the approved font, readings, and lyric timings otherwise intact.

Update the ASS video/audio project references and provenance to the new input. Record the actually downloaded DASH track dimensions and codec rather than copying a top-level quality label or maximum available resolution. Credit the actual rendering source and the original MV separately when both are known. Preserve a verified Bilibili source's suitable full-mix AAC with `-c:a copy` where possible, and verify packet identity.

## Bilibili transcoding diagnosis and repair

Compare a stuck part with a passing part before changing everything. Inspect video codec/profile/pixel format, color primaries/transfer/matrix, audio codec/rate/channels, stream start times and durations, packet PTS/DTS, and AAC skip/discard metadata. Decode the entire suspect file with errors treated as failures. Record observations separately from hypotheses: successful local decoding does not guarantee platform acceptance, and a generic “video data” or color-space message does not identify the defective stream.

Small audio/video duration differences on the scale of an audio packet or video frame are normal in many accepted MP4s. Compare with the passing part and source; do not diagnose a few milliseconds as the root cause or blindly pad/trim until printed durations match. Negative initial DTS from B-frame reordering or codec priming is also not, by itself, corruption. Look for nonmonotonic DTS, discontinuities, missing tail content, or a meaningful sync error.

For SDR compatibility, H.264/yuv420p with correctly signaled BT.709 and AAC stereo in faststart MP4 is a useful baseline. If NVENC output is suspect, a software x264 encode can isolate encoder-related compatibility; CRF 18–20 is a practical quality-preserving starting point, not a guaranteed file size. Encode from the best available source with the corrected ASS rather than repeatedly recompressing successive repairs. If only audio/container repair is needed, preserve the verified burned video with `-c:v copy`.

Treat reports about Gamma 2.6, H.265, or AAC/FLAC interactions as hypotheses unless the file and platform result support them. Inspect the actual transfer tags before blaming Gamma 2.6. Never relabel genuine HDR or gamma-encoded content as BT.709 without the appropriate color conversion. Rebuilding AAC and the MP4 container may help isolate timestamp/metadata issues; an unusual AAC trim value alone is not proof of failure.

When these checks do not establish a cause, try a complete matching Bilibili source according to the user's source preference, first verifying ASS synchronization. Keep a brief record of changed variables and the new upload CID. After authorized replacement, read back each part's state: upload/edit success, completed transcoding, and review/publication are separate milestones. Use bounded polling, report unresolved platform processing honestly, and do not repeatedly upload identical files merely because processing is slow.

## 视频截取 `t1`–`t2`

For an absolute-time, frame-accurate segment, combine a fast input-side seek with a precise output-side seek:

1. Choose a small seek margin before `t1` (for example 5–15 seconds, or the nearest known keyframe).
2. Put `-ss fast_start` before `-i` to jump quickly to the nearby keyframe without decoding the earlier portion.
3. Put `-ss precise_offset` after `-i`; FFmpeg then decodes from the nearby point until the exact `t1` boundary.
4. Use `-t t2-t1`, not `-to` relative to the original file, and re-encode the video/audio when exact boundaries are required.

Example for `t1=120.0`, `t2=150.0`, with a 10-second fast-seek margin:

```bash
ffmpeg -nostdin -y \
  -ss 110.0 -i input.mp4 -ss 10.0 -t 30.0 \
  -map 0:v:0 -map 0:a:0 \
  -c:v h264_nvenc -preset p5 -rc:v vbr -cq:v 19 -b:v 0 \
  -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -avoid_negative_ts make_zero -movflags +faststart clip.mp4
```

Input-side `-ss` alone is fast but keyframe-dependent. Pure `-c copy` can only cut accurately on existing packet/keyframe boundaries; do not promise absolute `t1`/`t2` accuracy with stream copy. Validate the clip duration and decode its first and last seconds with `ffprobe`/FFmpeg before handing it off.
