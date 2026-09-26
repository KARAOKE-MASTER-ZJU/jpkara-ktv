# Rendering and verification

Read this reference when burning ASS subtitles or producing on-vocal/off-vocal MP4 files.

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
