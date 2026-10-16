#!/usr/bin/env python3
"""Run FA-Kara alignment and copy its native o.ass to a chosen output."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fa-kara-dir", type=Path, default=Path.home() / "FA-Kara")
    parser.add_argument("--python", dest="python_bin", default=sys.executable)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--gpu", action="store_true", help="allow CUDA; CPU is the safe default")
    args = parser.parse_args()
    work_dir = (args.work_dir or args.output.parent).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if not args.gpu:
        env["CUDA_VISIBLE_DEVICES"] = ""
    command = [args.python_bin, str(args.fa_kara_dir / "main.py"), "-p", str(work_dir),
               "-ia", str(args.audio.resolve()), "-it", str(args.lyrics.resolve())]
    subprocess.run(command, cwd=args.fa_kara_dir, env=env, check=True)
    source = work_dir / "o.ass"
    if not source.exists():
        raise FileNotFoundError(f"FA-Kara did not produce {source}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, args.output)
    print(f"copied {source} to {args.output}")


if __name__ == "__main__":
    main()
