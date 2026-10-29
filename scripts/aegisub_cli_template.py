#!/usr/bin/env python3
"""Run Aegisub's interleave macro and karaoke templater on a result ASS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from fix_countdown_spacing import fix_file


ALIAS = "InterleaveK1K2"
BUNDLED_AUTOMATION = Path(__file__).resolve().parent.parent / "assets" / "aegisub-automation"
REGISTRATION = re.compile(
    r"for i = 1, #TLL_macros do\s*"
    r"aegisub\.register_macro\([^\n]*\)\s*end"
)
ALIAS_REGISTRATION = (
    'for i = 1, #TLL_macros do\n'
    '    if i == 2 then\n'
    '        aegisub.register_macro("InterleaveK1K2", "CLI alias", '
    'TLL_macros[i]["entry"], TLL_macros[i]["validation"])\n'
    '    end\n'
    'end'
)


def win_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)
    if sys.platform.startswith("linux") and "microsoft" in Path("/proc/version").read_text().lower():
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
    return str(path)


def prepared_helper(source: Path, destination: Path) -> None:
    lua = source.read_text(encoding="utf-8-sig")
    patched, count = REGISTRATION.subn(ALIAS_REGISTRATION, lua, count=1)
    if count != 1:
        raise ValueError("Cannot find Karaoke Helper registration loop; inspect the installed Lua script")
    destination.write_text(patched, encoding="utf-8")


def run_macro(cli: Path, script: Path, source: Path, target: Path, macro: str,
              dialog: dict | None = None, verbose: bool = False) -> None:
    cmd = [str(cli), "--automation", win_path(script)]
    if dialog is not None:
        cmd += ["--dialog", json.dumps({"button": 0, "values": dialog}, ensure_ascii=False)]
    cmd += [win_path(source), win_path(target), macro]
    try:
        subprocess.run(cmd, cwd=script.parent, check=True, capture_output=not verbose, text=True)
    except subprocess.CalledProcessError as error:
        if not verbose:
            print(((error.stdout or '') + (error.stderr or ''))[-6000:], file=sys.stderr)
        raise
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Aegisub CLI did not produce {target}")


def count_ass(path: Path) -> tuple[int, int]:
    body = path.read_text(encoding="utf-8-sig")
    return len(re.findall(r"^Dialogue: ", body, re.M)), len(re.findall(r"^Comment: ", body, re.M))


def discover_cli(explicit: Path | None) -> Path | None:
    candidates = [explicit]
    configured = os.environ.get("AEGISUB_CLI")
    if configured:
        candidates.append(Path(configured))
    on_path = shutil.which("aegisub-cli.exe") or shutil.which("aegisub-cli")
    if on_path:
        candidates.append(Path(on_path))
    return next((path.resolve() for path in candidates if path and path.is_file()), None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="result.ass or result_har.ass")
    parser.add_argument("--cli", type=Path, help="aegisub-cli.exe; defaults to AEGISUB_CLI or PATH")
    parser.add_argument("--helper", type=Path, default=BUNDLED_AUTOMATION / "autoload" / "karaoke-helper.lua",
                        help="defaults to the skill-bundled karaoke-helper.lua")
    parser.add_argument("--templater", type=Path, default=BUNDLED_AUTOMATION / "autoload" / "kara-templater.lua",
                        help="defaults to the skill-bundled kara-templater.lua")
    parser.add_argument("--output", type=Path, help="defaults to new.ass or new_har.ass")
    parser.add_argument("--scratch-parent", type=Path, help="ASCII-only Windows-accessible directory; defaults to CLI directory")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fix-countdown", action="store_true",
                        help="repair source Intro spacing before template expansion")
    parser.add_argument("--countdown-gap", type=float, help="countdown/ruby gap in pixels")
    parser.add_argument('--verbose', action='store_true', help='show full Aegisub automation logs')
    args = parser.parse_args()
    cli = discover_cli(args.cli)
    if cli is None:
        parser.error("aegisub-cli.exe not found; pass --cli or set AEGISUB_CLI")

    source = args.input.resolve()
    expected = {"result.ass": "new.ass", "result_har.ass": "new_har.ass"}
    if source.name.lower() not in expected:
        parser.error("Input must be named result.ass or result_har.ass")
    output = (args.output or source.with_name(expected[source.name.lower()])).resolve()
    if source == output:
        parser.error("Output must differ from input")
    for path in (source, cli, args.helper, args.templater):
        if not path.is_file():
            parser.error(f"File not found: {path}")
    if output.exists() and not args.overwrite:
        parser.error(f"Output already exists: {output}; use --overwrite to replace it")

    scratch_parent = (args.scratch_parent or cli.parent).resolve()
    if not scratch_parent.is_dir() or not str(scratch_parent).isascii():
        parser.error("Scratch parent must exist and have an ASCII-only path")
    # Keep the Lua default for the Unicode countdown glyph. Passing it via WSL
    # argv corrupts the glyph in this Windows CLI build.
    dialog = {"style": "Default", "advance_time": 2000, "extend_time": 1000,
              "sep_threshold": 4000, "countdown": True}
    if args.fix_countdown:
        print(json.dumps(fix_file(source, source, args.countdown_gap)))
    with tempfile.TemporaryDirectory(prefix="ktv_cli_", dir=scratch_parent) as scratch_name:
        scratch = Path(scratch_name)
        staged_input = scratch / "input.ass"
        staged_helper = scratch / "helper.lua"
        staged_templater = scratch / "templater.lua"
        stage1 = scratch / "interleaved.ass"
        stage2 = scratch / "templated.ass"
        shutil.copy2(source, staged_input)
        shutil.copy2(args.templater, staged_templater)
        prepared_helper(args.helper, staged_helper)
        run_macro(cli, staged_helper, staged_input, stage1, ALIAS, dialog, args.verbose)
        run_macro(cli, staged_templater, stage1, stage2, "Apply karaoke template", verbose=args.verbose)
        before, _ = count_ass(source)
        after, comments = count_ass(stage2)
        if before == 0 or after <= before or comments == 0:
            raise RuntimeError(f"Suspicious template output: before={before}, after={after}, comments={comments}")
        output.parent.mkdir(parents=True, exist_ok=True)
        staged_output = output.with_name(output.name + ".tmp")
        shutil.copy2(stage2, staged_output)
        os.replace(staged_output, output)
    print(f"Saved {output} (dialogues: {before} -> {after}, comments: {comments})")


if __name__ == "__main__":
    main()
