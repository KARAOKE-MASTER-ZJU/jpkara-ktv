#!/usr/bin/env python3
"""Normalize FA-Kara continuation readings to Aegisub/jpkara `#|<reading` syntax."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BARE_CONTINUATION = re.compile(r"#\|(?!<)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output: list[str] = []
    replacements = 0
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            if len(fields) == 10 and fields[8] == "karaoke":
                fields[9], count = BARE_CONTINUATION.subn("#|<", fields[9])
                replacements += count
                line = ",".join(fields)
        output.append(line)
    args.output.write_text("\n".join(output) + "\n", encoding="utf-8-sig")
    print(f"normalized {replacements} continuation readings; wrote {args.output}")


if __name__ == "__main__":
    main()
