#!/usr/bin/env python3
"""Burn one ASS video, then mux verified ON- and OFF-vocal MP4 outputs."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def probe(path: Path) -> dict:
    return json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ], capture=True))


def packet_md5(path: Path) -> str:
    output = run([
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-c", "copy", "-f", "md5", "-",
    ], capture=True)
    return output.partition("=")[2].strip()


def filter_escape(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{value}'"


def encoder_args(encoder: str) -> list[str]:
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc:v", "vbr", "-cq:v", "19", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def nvenc_listed() -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
    )
    return "h264_nvenc" in result.stdout


def burn_subtitles(video: Path, ass: Path, output: Path, requested: str) -> str:
    candidates = (["h264_nvenc", "libx264"] if requested == "auto" and nvenc_listed()
                  else ["libx264"] if requested == "auto" else [requested])
    last_error: subprocess.CalledProcessError | None = None
    for encoder in candidates:
        output.unlink(missing_ok=True)
        try:
            run([
                "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(video),
                "-map", "0:v:0", "-vf", filter_escape(ass), "-an",
                *encoder_args(encoder), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ])
            return encoder
        except subprocess.CalledProcessError as error:
            last_error = error
            if requested != "auto":
                raise
            print(f"{encoder} failed; trying software encoding")
    assert last_error is not None
    raise last_error


def validate_output(path: Path, expected_width: int, expected_height: int) -> None:
    info = probe(path)
    videos = [item for item in info["streams"] if item["codec_type"] == "video"]
    audios = [item for item in info["streams"] if item["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise SystemExit(f"{path}: expected exactly one video and one audio stream")
    video = videos[0]
    audio = audios[0]
    if video.get("codec_name") != "h264" or (video.get("width"), video.get("height")) != \
            (expected_width, expected_height):
        raise SystemExit(f"{path}: unexpected video stream")
    if audio.get("codec_name") != "aac" or int(audio.get("channels", 0)) != 2:
        raise SystemExit(f"{path}: expected stereo AAC audio")
    duration = float(info["format"]["duration"])
    run([
        "ffmpeg", "-v", "error", "-ss", str(max(0.0, duration - 1.0)),
        "-i", str(path), "-t", "1", "-f", "null", "-",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--ass", type=Path, required=True)
    parser.add_argument("--full-mix", type=Path,
                        help="audio source for ON VOCAL; defaults to --video")
    parser.add_argument("--instrumental", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True,
                        help="writes PREFIX_ON_VOCAL.mp4 and PREFIX_OFF_VOCAL.mp4")
    parser.add_argument("--encoder", choices=("auto", "h264_nvenc", "libx264"), default="auto")
    parser.add_argument("--off-bitrate", default="192k")
    parser.add_argument("--preview-png", type=Path,
                        help="optional screenshot from the burned video")
    parser.add_argument("--preview-at", type=float, default=8.0)
    parser.add_argument("--subbed-output", type=Path,
                        help="optionally retain the silent burned-in video")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    video = args.video.resolve()
    ass = args.ass.resolve()
    full_mix = (args.full_mix or args.video).resolve()
    instrumental = args.instrumental.resolve()
    prefix = args.output_prefix.resolve()
    on_output = prefix.parent / f"{prefix.name}_ON_VOCAL.mp4"
    off_output = prefix.parent / f"{prefix.name}_OFF_VOCAL.mp4"
    preview_output = args.preview_png.resolve() if args.preview_png else None
    subbed_output = args.subbed_output.resolve() if args.subbed_output else None
    for path in (video, ass, full_mix, instrumental):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    destinations = [on_output, off_output]
    if preview_output:
        destinations.append(preview_output)
    if subbed_output:
        destinations.append(subbed_output)
    if len(set(destinations)) != len(destinations):
        parser.error("output paths must be distinct")
    for path in destinations:
        if path.exists() and not args.overwrite:
            parser.error(f"output exists; pass --overwrite to replace it: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    video_info = probe(video)
    video_stream = next((item for item in video_info["streams"] if item["codec_type"] == "video"), None)
    if not video_stream:
        parser.error(f"no video stream in {video}")
    width, height = int(video_stream["width"]), int(video_stream["height"])
    full_audio = next((item for item in probe(full_mix)["streams"] if item["codec_type"] == "audio"), None)
    if not full_audio:
        parser.error(f"no audio stream in {full_mix}")
    if full_audio.get("codec_name") != "aac":
        parser.error("ON VOCAL bit-copying to MP4 requires AAC full-mix audio")

    with tempfile.TemporaryDirectory(prefix="jpkara-render-", dir=prefix.parent) as temp_name:
        temp = Path(temp_name)
        subbed = temp / "subbed.mp4"
        encoder = burn_subtitles(video, ass, subbed, args.encoder)
        on_temp = temp / "on-vocal.mp4"
        off_temp = temp / "off-vocal.mp4"
        run([
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(subbed),
            "-i", str(full_mix), "-map", "0:v:0", "-map", "1:a:0",
            # Do not use -shortest: a one-frame/video-timestamp difference can
            # silently drop the last packet of the bit-copied ON track.
            "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart",
            str(on_temp),
        ])
        run([
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(subbed),
            "-i", str(instrumental), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", args.off_bitrate, "-ac", "2",
            "-movflags", "+faststart", str(off_temp),
        ])

        validate_output(on_temp, width, height)
        validate_output(off_temp, width, height)
        source_md5 = packet_md5(full_mix)
        on_md5 = packet_md5(on_temp)
        if not source_md5 or source_md5 != on_md5:
            raise SystemExit("ON VOCAL audio packet MD5 mismatch; refusing to publish outputs")
        if preview_output:
            subbed_duration = float(probe(subbed)["format"]["duration"])
            preview_time = min(max(0.0, args.preview_at), max(0.0, subbed_duration - 0.05))
            run([
                "ffmpeg", "-nostdin", "-hide_banner", "-y", "-ss", str(preview_time),
                "-i", str(subbed), "-frames:v", "1", str(temp / "preview.png"),
            ])
            if not (temp / "preview.png").is_file():
                raise SystemExit("preview extraction produced no image")
            shutil.copy2(temp / "preview.png", preview_output)
        if subbed_output:
            shutil.copy2(subbed, subbed_output)
        on_temp.replace(on_output)
        off_temp.replace(off_output)

    print(f"wrote ON VOCAL: {on_output}")
    print(f"wrote OFF VOCAL: {off_output}")
    print(f"video encoded once with {encoder}; ON audio packet MD5 preserved: {source_md5}")


if __name__ == "__main__":
    main()
