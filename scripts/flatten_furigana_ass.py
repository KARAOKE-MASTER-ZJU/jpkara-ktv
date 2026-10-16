#!/usr/bin/env python3
"""Flatten jpkara furigana groups into one karaoke source line per ASS event."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

K_TAG = re.compile(r"\{\\k(\d+)\}")


def parse_time(value: str) -> int:
    hour, minute, rest = value.split(":")
    second, centisecond = rest.split(".")
    return ((int(hour) * 60 + int(minute)) * 60 + int(second)) * 100 + int(centisecond)


def format_time(value: int) -> str:
    value = max(0, value)
    hour, value = divmod(value, 360000)
    minute, value = divmod(value, 6000)
    second, centisecond = divmod(value, 100)
    return f"{hour}:{minute:02d}:{second:02d}.{centisecond:02d}"


def flatten(text: str) -> tuple[str, int, int]:
    matches = list(K_TAG.finditer(text))
    if not matches:
        return text, 0, 0
    prefix = text[: matches[0].start()]
    source = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        source.append([int(match.group(1)), text[match.end():end]])

    flat: list[list[int | str]] = []
    furigana_target: int | None = None
    for duration, chunk in source:
        if "|<" in chunk:
            surface, _reading = chunk.split("|<", 1)
            flat.append([duration, surface])
            furigana_target = len(flat) - 1
        elif chunk.startswith("#|") and furigana_target is not None:
            flat[furigana_target][0] = int(flat[furigana_target][0]) + duration
        else:
            flat.append([duration, chunk])
            furigana_target = None

    leading = 0
    while flat and not str(flat[0][1]):
        leading += int(flat.pop(0)[0])
    trailing = 0
    while flat and not str(flat[-1][1]):
        trailing += int(flat.pop()[0])
    # Internal empty syllables are timing only; merge them backward where possible.
    merged: list[list[int | str]] = []
    for duration, chunk in flat:
        if not str(chunk) and merged:
            merged[-1][0] = int(merged[-1][0]) + int(duration)
        else:
            merged.append([duration, chunk])
    flattened = prefix + "".join(f"{{\\k{duration}}}{chunk}" for duration, chunk in merged)
    return flattened, leading, trailing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output: list[str] = []
    changed = 0
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            if len(fields) == 10 and fields[8] == "karaoke":
                fields[9], leading, trailing = flatten(fields[9])
                fields[1] = format_time(parse_time(fields[1]) + leading)
                fields[2] = format_time(parse_time(fields[2]) - trailing)
                line = ",".join(fields)
                changed += 1
        output.append(line)
    args.output.write_text("\n".join(output) + "\n", encoding="utf-8-sig")
    print(f"flattened {changed} karaoke lines; wrote {args.output}")


if __name__ == "__main__":
    main()
