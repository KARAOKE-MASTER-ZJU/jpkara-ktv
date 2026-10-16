#!/usr/bin/env python3
"""Generate FA-Kara {surface|reading} lyrics with jpkara/YOHANE."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


KANJI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々]")


def is_kana(char: str) -> bool:
    return "\u3040" <= char <= "\u30ff" or char == "ー"


def format_pair(surface: str, reading: str) -> str:
    """Annotate kanji runs only; leave matching okurigana outside braces."""
    if not reading or not KANJI.search(surface):
        return surface
    runs: list[tuple[bool, str]] = []
    for char in surface:
        kana = is_kana(char)
        if runs and runs[-1][0] == kana:
            runs[-1] = (kana, runs[-1][1] + char)
        else:
            runs.append((kana, char))
    output: list[str] = []
    cursor = 0
    for index, (kana, text) in enumerate(runs):
        if kana:
            if not reading.startswith(text, cursor):
                return f"{{{surface}|{reading}}}"
            output.append(text)
            cursor += len(text)
            continue
        next_kana = next((value for flag, value in runs[index + 1:] if flag), None)
        end = reading.find(next_kana, cursor) if next_kana is not None else len(reading)
        if end < cursor:
            return f"{{{surface}|{reading}}}"
        part_reading = reading[cursor:end]
        output.append(f"{{{text}|{part_reading}}}" if KANJI.search(text) else text)
        cursor = end
    return "".join(output) if cursor == len(reading) else f"{{{surface}|{reading}}}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jpkara-dir", type=Path, default=Path.cwd())
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--no-rl", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.jpkara_dir))
    from dotenv import load_dotenv
    from jpkara.pipeline import Pipeline

    load_dotenv(args.jpkara_dir / ".env")
    analyzer = Pipeline(use_rl=not args.no_rl, use_llm=not args.no_llm).analyzer
    lines = args.input.read_text(encoding="utf-8").splitlines()
    converted: list[str] = []
    errors = 0
    for line in lines:
        if not line.strip():
            converted.append("")
            continue
        if args.no_llm:
            pairs, error = analyzer._tokenize_and_rl(line)
        else:
            mapping, error = analyzer._llm.annotate_lines([line])
            pairs = mapping.get(0) if mapping else None
            pairs = pairs or analyzer._tokenize_and_rl(line)[0]
        if error:
            errors += 1
        converted.append("".join(format_pair(surface, reading) for surface, reading in pairs))
    args.output.write_text("\n".join(converted) + ("\n" if converted else ""), encoding="utf-8")
    print(f"wrote {len(lines)} lines to {args.output}; annotation errors: {errors}")


if __name__ == "__main__":
    main()
