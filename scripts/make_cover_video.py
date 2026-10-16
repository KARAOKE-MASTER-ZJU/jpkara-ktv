#!/usr/bin/env python3
"""Build a blurred 16:9 cover video while bit-copying the source audio."""
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


def video_dimensions(path: Path) -> tuple[int, int]:
    stream = next((item for item in probe(path)["streams"] if item["codec_type"] == "video"), None)
    if not stream:
        raise SystemExit(f"no video stream in {path}")
    return int(stream["width"]), int(stream["height"])


def audio_packet_md5(path: Path) -> str:
    output = run([
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-c", "copy", "-f", "md5", "-",
    ], capture=True)
    return output.partition("=")[2].strip()


def parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = (int(item) for item in value.lower().split("x", 1))
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT") from error
    if width < 2 or height < 2:
        raise argparse.ArgumentTypeError("canvas dimensions must be at least 2")
    return width, height


def parse_crop(value: str) -> tuple[int, int, int, int]:
    try:
        values = [int(item) for item in value.split(":")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected X:Y:SIZE or X:Y:WIDTH:HEIGHT") from error
    if len(values) == 3:
        x, y, size = values
        values = [x, y, size, size]
    if len(values) != 4 or min(values) < 0 or values[2] < 1 or values[3] < 1:
        raise argparse.ArgumentTypeError("expected non-negative X:Y and positive dimensions")
    return tuple(values)  # type: ignore[return-value]


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


def encode_loop(still: Path, output: Path, fps: int, requested: str) -> str:
    candidates = (["h264_nvenc", "libx264"] if requested == "auto" and nvenc_listed()
                  else ["libx264"] if requested == "auto" else [requested])
    last_error: subprocess.CalledProcessError | None = None
    for encoder in candidates:
        output.unlink(missing_ok=True)
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-loop", "1",
            "-framerate", str(fps), "-i", str(still), "-t", "1", "-an",
            *encoder_args(encoder), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output),
        ]
        try:
            run(command)
            return encoder
        except subprocess.CalledProcessError as error:
            last_error = error
            if requested != "auto":
                raise
            print(f"{encoder} failed; trying software encoding")
    assert last_error is not None
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-video", type=Path, required=True,
                        help="video whose first audio stream and duration are preserved")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cover-image", type=Path,
                        help="clean cover image; otherwise crop it from a source-video frame")
    parser.add_argument("--frame-time", type=float, default=1.0)
    parser.add_argument("--crop", type=parse_crop,
                        help="frame crop as X:Y:SIZE or X:Y:WIDTH:HEIGHT")
    parser.add_argument("--canvas", type=parse_size, default=(1920, 1080))
    parser.add_argument("--cover-size", type=int, default=500)
    parser.add_argument("--cover-y", type=int, default=330)
    parser.add_argument("--blur-sigma", type=float, default=12.0)
    parser.add_argument("--brightness", type=float, default=-0.07)
    parser.add_argument("--saturation", type=float, default=0.9)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--encoder", choices=("auto", "h264_nvenc", "libx264"), default="auto")
    parser.add_argument("--still-output", type=Path,
                        help="defaults to OUTPUT with a .png suffix")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source = args.source_video.resolve()
    output = args.output.resolve()
    still_output = (args.still_output or output.with_suffix(".png")).resolve()
    cover_image = args.cover_image.resolve() if args.cover_image else None
    for path in (source, cover_image):
        if path is not None and not path.is_file():
            parser.error(f"file not found: {path}")
    if output == still_output:
        parser.error("video and still outputs must differ")
    for path in (output, still_output):
        if path.exists() and not args.overwrite:
            parser.error(f"output exists; pass --overwrite to replace it: {path}")

    canvas_width, canvas_height = args.canvas
    if args.cover_size < 1 or args.cover_size > min(canvas_width, canvas_height):
        parser.error("--cover-size must fit inside the canvas")
    if args.cover_y < 0 or args.cover_y + args.cover_size > canvas_height:
        parser.error("--cover-y places the cover outside the canvas")
    if args.blur_sigma < 0 or not -1 <= args.brightness <= 1 or args.saturation < 0:
        parser.error("invalid blur/brightness/saturation value")
    if args.fps < 1:
        parser.error("--fps must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    still_output.parent.mkdir(parents=True, exist_ok=True)

    source_info = probe(source)
    audio = next((item for item in source_info["streams"] if item["codec_type"] == "audio"), None)
    if not audio:
        parser.error(f"no audio stream in {source}")
    if audio.get("codec_name") != "aac":
        parser.error("bit-copying to MP4 currently requires an AAC source audio stream")

    with tempfile.TemporaryDirectory(prefix="jpkara-cover-", dir=output.parent) as temp_name:
        temp = Path(temp_name)
        cover = temp / "cover.png"
        if cover_image:
            shutil.copy2(cover_image, cover)
        else:
            source_width, source_height = video_dimensions(source)
            crop = args.crop
            if crop is None:
                size = min(source_width, source_height)
                crop = ((source_width - size) // 2, (source_height - size) // 2, size, size)
                print(f"no --crop supplied; using centered crop {crop[0]}:{crop[1]}:{size}:{size}")
            x, y, width, height = crop
            if x + width > source_width or y + height > source_height:
                parser.error(f"crop {crop} exceeds source frame {source_width}x{source_height}")
            run([
                "ffmpeg", "-nostdin", "-hide_banner", "-y", "-ss", str(args.frame_time),
                "-i", str(source), "-vf", f"crop={width}:{height}:{x}:{y}",
                "-frames:v", "1", str(cover),
            ])

        cover_width, cover_height = video_dimensions(cover)
        square = min(cover_width, cover_height)
        square_x = (cover_width - square) // 2
        square_y = (cover_height - square) // 2
        still = temp / "cover-background.png"
        filters = (
            f"[0:v]crop={square}:{square}:{square_x}:{square_y},split=2[fg][bg];"
            f"[bg]scale={canvas_width}:{canvas_height}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={canvas_width}:{canvas_height},gblur=sigma={args.blur_sigma},"
            f"eq=brightness={args.brightness}:saturation={args.saturation}[bg2];"
            f"[fg]scale={args.cover_size}:{args.cover_size}:flags=lanczos[fg2];"
            f"[bg2][fg2]overlay=(W-w)/2:{args.cover_y}:format=auto"
        )
        run([
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(cover),
            "-filter_complex", filters, "-frames:v", "1", str(still),
        ])

        loop = temp / "cover-loop.mp4"
        encoder = encode_loop(still, loop, args.fps, args.encoder)
        rendered = temp / "cover-video.mp4"
        run([
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-stream_loop", "-1",
            "-i", str(loop), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart",
            str(rendered),
        ])

        input_md5 = audio_packet_md5(source)
        output_md5 = audio_packet_md5(rendered)
        if not input_md5 or input_md5 != output_md5:
            raise SystemExit("audio packet MD5 mismatch; refusing to publish output")
        rendered_info = probe(rendered)
        streams = rendered_info["streams"]
        if [item["codec_type"] for item in streams].count("video") != 1 or \
                [item["codec_type"] for item in streams].count("audio") != 1:
            raise SystemExit("expected exactly one video and one audio stream")

        shutil.copy2(still, still_output)
        rendered.replace(output)

    print(f"wrote still: {still_output}")
    print(f"wrote video: {output}")
    print(f"video encoder: {encoder}; source audio packet MD5 preserved: {input_md5}")


if __name__ == "__main__":
    main()
