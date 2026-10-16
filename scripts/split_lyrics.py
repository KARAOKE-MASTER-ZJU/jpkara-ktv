#!/usr/bin/env python3
"""Split long lyric lines without breaking ASCII words."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?|[^A-Za-z0-9]")


def split_line(line: str, limit: int) -> list[str]:
    if len(line) <= limit:
        return [line]
    tokens = TOKEN_RE.findall(line)
    chunks: list[str] = []
    current = ""
    for token in tokens:
        if current and len(current) + len(token) > limit:
            chunks.append(current)
            current = ""
        current += token
    if current:
        chunks.append(current)
    return chunks or [line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-chars", type=int, default=15)
    args = parser.parse_args()
    if args.max_chars < 1:
        parser.error("--max-chars must be positive")
    lines = args.input.read_text(encoding="utf-8").splitlines()
    result = [part for line in lines for part in split_line(line, args.max_chars)]
    args.output.write_text("\n".join(result) + ("\n" if result else ""), encoding="utf-8")
    print(f"wrote {len(result)} lines to {args.output}")


if __name__ == "__main__":
    main()
