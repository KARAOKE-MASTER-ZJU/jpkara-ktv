#!/usr/bin/env python3
"""Rewrite FA-Kara readings so ruby covers kanji only, not okurigana."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from yohane_readings_to_fa import format_pair

PAIR = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        original = match.group(0)
        normalized = format_pair(match.group(1), match.group(2))
        changed += normalized != original
        return normalized

    text = PAIR.sub(replace, args.input.read_text(encoding="utf-8"))
    args.output.write_text(text, encoding="utf-8")
    print(f"normalized {changed} mixed kanji/okurigana groups; wrote {args.output}")


if __name__ == "__main__":
    main()
