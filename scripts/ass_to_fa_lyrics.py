#!/usr/bin/env python3
"""Convert jpkara karaoke ASS dialogue text to FA-Kara reading syntax."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

K_TAG = re.compile(r"\{\\k\d+\}")
READING = re.compile(r"([^|{}]*)\|<([^{}]*)")


def convert(text: str) -> str:
    text = K_TAG.sub("", text)
    out: list[str] = []
    for match in READING.finditer(text):
        surface, reading = match.groups()
        surface = surface.strip()
        reading = reading.strip()
        if surface and reading:
            out.append(f"{{{surface}|{reading}}}")
    return "".join(out) if out else re.sub(r"\{[^}]*\}", "", text).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    lines = []
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            lines.append(convert(fields[9] if len(fields) == 10 else line))
    args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"wrote {len(lines)} lines to {args.output}")


if __name__ == "__main__":
    main()
