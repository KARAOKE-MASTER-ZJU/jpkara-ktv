#!/usr/bin/env python3
"""Scale ASS style geometry while preserving colors and karaoke timing."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--from-size", type=float, default=130)
    parser.add_argument("--to-size", type=float, default=108)
    args = parser.parse_args()
    if args.from_size <= 0 or args.to_size <= 0:
        parser.error("font sizes must be positive")
    factor = args.to_size / args.from_size
    # Fontsize, outline, shadow, and the three margins are pixel-like geometry.
    geometry = {2, 16, 17, 19, 20, 21}
    integer_geometry = {2, 19, 20, 21}  # required integer fields in Aegisub ASS styles
    out: list[str] = []
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("Style:"):
            fields = line.split(",")
            for index in geometry:
                value = float(fields[index]) * factor
                if index in integer_geometry:
                    fields[index] = str(max(0, int(round(value))))
                else:
                    fields[index] = f"{value:.2f}".rstrip("0").rstrip(".")
            line = ",".join(fields)
        out.append(line)
    args.output.write_text("\n".join(out) + "\n", encoding="utf-8-sig")
    print(f"scaled styles by {factor:.8f}; wrote {args.output}")


if __name__ == "__main__":
    main()
