#!/usr/bin/env python3
"""Keep furigana only above kanji and return okurigana to the ASS base text."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

K_TOKEN = re.compile(r"(\{\\k\d+\})([^{}]*)")
KANJI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々]")


def is_kana(char: str) -> bool:
    return "\u3040" <= char <= "\u30ff" or char == "ー"


def surface_segments(surface: str, reading: str) -> list[tuple[str, str, bool]] | None:
    runs: list[tuple[bool, str]] = []
    for char in surface:
        kana = is_kana(char)
        if runs and runs[-1][0] == kana:
            runs[-1] = (kana, runs[-1][1] + char)
        else:
            runs.append((kana, char))
    result: list[tuple[str, str, bool]] = []
    cursor = 0
    for index, (kana, text) in enumerate(runs):
        if kana:
            if not reading.startswith(text, cursor):
                return None
            result.append((text, text, False))
            cursor += len(text)
            continue
        next_kana = next((value for flag, value in runs[index + 1:] if flag), None)
        end = reading.find(next_kana, cursor) if next_kana is not None else len(reading)
        if end < cursor:
            return None
        result.append((text, reading[cursor:end], bool(KANJI.search(text))))
        cursor = end
    return result if cursor == len(reading) else None


def rewrite_group(surface: str, tokens: list[tuple[str, str]]) -> str | None:
    reading = "".join(text for _tag, text in tokens)
    segments = surface_segments(surface, reading)
    if not segments:
        return None
    work = [[tag, text] for tag, text in tokens]
    token_index = 0
    output: list[str] = []
    for base, target, use_furigana in segments:
        consumed: list[tuple[str, str]] = []
        current = ""
        while token_index < len(work) and len(current) < len(target):
            tag, text = work[token_index]
            needed = len(target) - len(current)
            if len(text) <= needed:
                consumed.append((tag, text))
                current += text
                token_index += 1
            else:
                consumed.append((tag, text[:needed]))
                current += text[:needed]
                work[token_index] = ["{\\k0}", text[needed:]]
        if current != target or not consumed:
            return None
        if not use_furigana and len(consumed) > 1:
            zero_prefix = ""
            while consumed and consumed[0][0] == "{\\k0}":
                zero_prefix += consumed.pop(0)[1]
            if zero_prefix and consumed:
                consumed[0] = (consumed[0][0], zero_prefix + consumed[0][1])
        for part_index, (tag, text) in enumerate(consumed):
            if use_furigana:
                marker = f"{base}|<" if part_index == 0 else "#|<"
                output.append(tag + marker + text)
            else:
                output.append(tag + text)
    return "".join(output) if token_index == len(work) else None


def rewrite_text(text: str) -> tuple[str, int]:
    tokens = [(m.group(1), m.group(2)) for m in K_TOKEN.finditer(text)]
    prefix = text[: K_TOKEN.search(text).start()] if tokens else text
    output: list[str] = [prefix]
    changed = 0
    index = 0
    while index < len(tokens):
        tag, chunk = tokens[index]
        if "|<" not in chunk or chunk.startswith("#|"):
            output.append(tag + chunk)
            index += 1
            continue
        surface, first_reading = chunk.split("|<", 1)
        group = [(tag, first_reading)]
        end = index + 1
        while end < len(tokens) and tokens[end][1].startswith("#|<"):
            group.append((tokens[end][0], tokens[end][1][3:]))
            end += 1
        rewritten = rewrite_group(surface, group)
        if rewritten is None:
            output.extend(t + c for t, c in tokens[index:end])
        else:
            output.append(rewritten)
            changed += 1
        index = end
    return "".join(output), changed


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
                fields[9], count = rewrite_text(fields[9])
                changed += count
                line = ",".join(fields)
        output.append(line)
    args.output.write_text("\n".join(output) + "\n", encoding="utf-8-sig")
    print(f"fixed okurigana in {changed} furigana groups; wrote {args.output}")


if __name__ == "__main__":
    main()
