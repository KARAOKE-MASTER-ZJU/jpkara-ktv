#!/usr/bin/env python3
"""Burn one ASS video, then mux verified ON- and OFF-vocal MP4 outputs."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import re
from pathlib import Path


def run(command: list[str], *, capture: bool = False, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        cwd=cwd,
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


def encoder_args(encoder: str, quality: float | None = None, preset: str | None = None) -> list[str]:
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", preset or "p5", "-tune", "hq",
                "-rc:v", "vbr", "-cq:v", str(19 if quality is None else quality), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", preset or "medium", "-crf", str(18 if quality is None else quality)]


def merge_ass(main: Path, harmony: Path, output: Path) -> None:
    """Merge expanded effects, refusing conflicting geometry/styles."""
    body = main.read_text(encoding="utf-8-sig").splitlines()
    other = harmony.read_text(encoding="utf-8-sig").splitlines()
    for key in ("PlayResX", "PlayResY"):
        values = [re.search(rf"^{key}:\s*(\d+)", text, re.M) for text in ("\n".join(body), "\n".join(other))]
        if not all(values) or values[0][1] != values[1][1]:
            raise ValueError(f"ASS {key} mismatch")
    styles = {x.split(',', 1)[0]: x for x in body if x.startswith('Style:')}
    additions = []
    for line in other:
        if line.startswith('Style:'):
            name = line.split(',', 1)[0]
            if name in styles and styles[name] != line:
                raise ValueError(f"Conflicting ASS style: {name}")
            if name not in styles:
                additions.append(line)
                styles[name] = line
    index = max(i for i, x in enumerate(body) if x.startswith('Style:')) + 1
    body[index:index] = additions
    body.extend(x for x in other if x.startswith('Dialogue:'))
    output.write_text('\n'.join(body) + '\n', encoding='utf-8-sig')


def nvenc_listed() -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
    )
    return "h264_nvenc" in result.stdout


def burn_subtitles(video: Path, ass: Path, output: Path, requested: str,
                   quality: float | None = None, preset: str | None = None,
                   dimensions: tuple[int, int] | None = None, threads: int | None = None) -> str:
    candidates = (["h264_nvenc", "libx264"] if requested == "auto" and nvenc_listed()
                  else ["libx264"] if requested == "auto" else [requested])
    last_error: subprocess.CalledProcessError | None = None
    staged_ass = output.parent / 'render.ass'
    if ass.resolve() != staged_ass.resolve():
        shutil.copy2(ass, staged_ass)
    for encoder in candidates:
        output.unlink(missing_ok=True)
        try:
            print(f'Encoding subtitles with {encoder}', flush=True)
            filters = ([f"scale={dimensions[0]}:{dimensions[1]}"] if dimensions else []) + ['subtitles=render.ass']
            run([
                "ffmpeg", "-nostdin", "-v", "error", "-nostats", "-y", "-i", str(video),
                "-map", "0:v:0", "-vf", ','.join(filters), "-an",
                *encoder_args(encoder, quality, preset),
                *(["-threads", str(threads)] if threads else []),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ], cwd=output.parent)
            return encoder
        except subprocess.CalledProcessError as error:
            last_error = error
            if requested != "auto":
                raise
            print(f"{encoder} failed; trying software encoding")
    assert last_error is not None
    raise last_error


def validate_output(path: Path, expected_width: int, expected_height: int, full: bool = False) -> dict:
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
    run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
         *([] if full else ["-ss", str(max(0.0, duration - 1.0))]),
         "-i", str(path), *([] if full else ["-t", "1"]), "-f", "null", "-"])
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--ass", type=Path, required=True)
    parser.add_argument("--harmony-ass", type=Path, help="expanded harmony ASS to merge automatically")
    parser.add_argument("--mode", choices=("on", "off", "both"), default="both")
    parser.add_argument("--full-mix", type=Path,
                        help="audio source for ON VOCAL; defaults to --video")
    parser.add_argument("--instrumental", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True,
                        help="writes PREFIX_ON_VOCAL.mp4 and PREFIX_OFF_VOCAL.mp4")
    parser.add_argument("--encoder", choices=("auto", "h264_nvenc", "libx264"), default="auto")
    parser.add_argument("--off-bitrate", default="192k")
    parser.add_argument("--on-audio", choices=("auto", "copy", "aac"), default="auto",
                        help="auto copies stereo AAC; otherwise encodes full mix once")
    parser.add_argument("--on-bitrate", default="192k")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--quality", type=float, help="x264 CRF / NVENC CQ")
    parser.add_argument("--preset", help="encoder-specific preset")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--verify", choices=("tail", "full"), default="tail")
    parser.add_argument("--report", type=Path, help="defaults to PREFIX_render.json")
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
    instrumental = args.instrumental.resolve() if args.instrumental else None
    want_on, want_off = args.mode != 'off', args.mode != 'on'
    if want_off and instrumental is None:
        parser.error('--instrumental is required for off/both modes')
    if bool(args.width) != bool(args.height) or any(x is not None and (x <= 0 or x % 2) for x in (args.width, args.height)):
        parser.error('--width and --height must be supplied together as positive even integers')
    if args.quality is not None and not 0 <= args.quality <= 51:
        parser.error('--quality must be between 0 and 51')
    if args.threads is not None and args.threads <= 0:
        parser.error('--threads must be positive')
    prefix = args.output_prefix.resolve()
    on_output = prefix.parent / f"{prefix.name}_ON_VOCAL.mp4"
    off_output = prefix.parent / f"{prefix.name}_OFF_VOCAL.mp4"
    preview_output = args.preview_png.resolve() if args.preview_png else None
    subbed_output = args.subbed_output.resolve() if args.subbed_output else None
    inputs = [video, ass] + ([full_mix] if want_on else []) + ([instrumental] if want_off else [])
    if args.harmony_ass:
        inputs.append(args.harmony_ass.resolve())
    for path in inputs:
        if not path.is_file():
            parser.error(f"file not found: {path}")
    destinations = ([on_output] if want_on else []) + ([off_output] if want_off else [])
    report_output = args.report.resolve() if args.report else prefix.with_name(prefix.name + '_render.json')
    destinations.append(report_output)
    if preview_output:
        destinations.append(preview_output)
    if subbed_output:
        destinations.append(subbed_output)
    if len(set(destinations)) != len(destinations):
        parser.error("output paths must be distinct")
    if set(destinations) & set(inputs):
        parser.error('outputs must not overwrite input media or ASS')
    for path in destinations:
        if path.exists() and not args.overwrite:
            parser.error(f"output exists; pass --overwrite to replace it: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    video_info = probe(video)
    video_stream = next((item for item in video_info["streams"] if item["codec_type"] == "video"), None)
    if not video_stream:
        parser.error(f"no video stream in {video}")
    width, height = int(video_stream["width"]), int(video_stream["height"])
    dimensions = (args.width, args.height) if args.width else None
    if dimensions:
        width, height = dimensions
    copy_audio = False
    if want_on:
        full_audio = next((item for item in probe(full_mix)["streams"] if item["codec_type"] == "audio"), None)
        if not full_audio:
            parser.error(f"no audio stream in {full_mix}")
        suitable = full_audio.get('codec_name') == 'aac' and full_audio.get('channels') == 2
        if args.on_audio == 'copy' and not suitable:
            parser.error('--on-audio copy requires stereo AAC')
        copy_audio = suitable and args.on_audio != 'aac'

    with tempfile.TemporaryDirectory(prefix="jpkara-render-", dir=prefix.parent) as temp_name:
        temp = Path(temp_name)
        render_ass = ass
        if args.harmony_ass:
            render_ass = temp / 'merged.ass'
            merge_ass(ass, args.harmony_ass.resolve(), render_ass)
        subbed = temp / "subbed.mp4"
        encoder = burn_subtitles(video, render_ass, subbed, args.encoder,
                                  args.quality, args.preset, dimensions, args.threads)
        on_temp = temp / "on-vocal.mp4"
        off_temp = temp / "off-vocal.mp4"
        if want_on:
            run([
                "ffmpeg", "-nostdin", "-v", "error", "-nostats", "-y", "-i", str(subbed),
                "-i", str(full_mix), "-map", "0:v:0", "-map", "1:a:0",
                # -shortest can drop the last packet of bit-copied ON audio.
                "-c:v", "copy", *(["-c:a", "copy"] if copy_audio else
                                    ["-c:a", "aac", "-b:a", args.on_bitrate, "-ar", "48000", "-ac", "2"]),
                "-movflags", "+faststart", str(on_temp),
            ])
        if want_off:
            run([
                "ffmpeg", "-nostdin", "-v", "error", "-nostats", "-y", "-i", str(subbed),
                "-i", str(instrumental), "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", args.off_bitrate, "-ac", "2",
                "-movflags", "+faststart", str(off_temp),
            ])

        outputs = {}
        print(f'Verifying {args.mode} output ({args.verify})', flush=True)
        if want_on:
            outputs['on'] = validate_output(on_temp, width, height, args.verify == 'full')
        if want_off:
            outputs['off'] = validate_output(off_temp, width, height, args.verify == 'full')
        source_md5 = packet_md5(full_mix) if copy_audio else None
        if copy_audio and (not source_md5 or source_md5 != packet_md5(on_temp)):
            raise SystemExit("ON VOCAL audio packet MD5 mismatch; refusing to publish outputs")
        if preview_output:
            subbed_duration = float(probe(subbed)["format"]["duration"])
            preview_time = min(max(0.0, args.preview_at), max(0.0, subbed_duration - 0.05))
            run([
                "ffmpeg", "-nostdin", "-v", "error", "-nostats", "-y", "-ss", str(preview_time),
                "-i", str(subbed), "-frames:v", "1", str(temp / "preview.png"),
            ])
            if not (temp / "preview.png").is_file():
                raise SystemExit("preview extraction produced no image")
            shutil.copy2(temp / "preview.png", preview_output)
        if subbed_output:
            shutil.copy2(subbed, subbed_output)
        if want_on:
            on_temp.replace(on_output)
            outputs['on']['format']['filename'] = str(on_output)
        if want_off:
            off_temp.replace(off_output)
            outputs['off']['format']['filename'] = str(off_output)
        report_output.write_text(json.dumps({'encoder': encoder, 'mode': args.mode,
            'video': str(video), 'ass': str(ass), 'quality': args.quality,
            'dimensions': [width, height],
            'on_audio': 'copy' if copy_audio else ('aac' if want_on else None),
            'on_audio_packet_md5': source_md5, 'verification': args.verify,
            'outputs': outputs}, ensure_ascii=False, indent=2))

    print(f"video encoded once with {encoder}; mode={args.mode}; ON audio={'copy' if copy_audio else 'aac'}")
    print(f"verification report: {report_output}")


if __name__ == "__main__":
    main()
