#!/usr/bin/env python3
"""Move source ASS countdown above the upper lyric/ruby effects; timing is unchanged."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re


def fix_spacing(body: str, gap: float | None = None) -> tuple[str, dict]:
    lines = body.splitlines()
    if any(line.startswith('Dialogue:') and ',fx,' in line for line in lines):
        raise ValueError('Use source result.ass, not an expanded effect ASS')
    height_match = re.search(r'^PlayResY:\s*(\d+)', body, re.M)
    if not height_match:
        raise ValueError('Missing PlayResY')
    height = int(height_match[1])
    scale = height / 1080
    gap = 24 * scale if gap is None else gap
    if gap < 0:
        raise ValueError('Gap must be nonnegative')
    styles = {}
    fields = []
    section = ''
    for index, line in enumerate(lines):
        if line.startswith('['):
            section = line
        if section == '[V4+ Styles]' and line.startswith('Format:'):
            fields = [f.strip() for f in line.partition(':')[2].split(',')]
        if section == '[V4+ Styles]' and line.startswith('Style:'):
            values = line.partition(':')[2].strip().split(',')
            if len(values) != len(fields):
                raise ValueError('Invalid ASS style format')
            item = dict(zip(fields, values))
            styles[item['Name']] = (index, values, item)
    if not {'Intro', 'K1'}.issubset(styles):
        raise ValueError('Expected Intro and K1 styles from the K1/K2 template')
    main, intro = styles['K1'][2], styles['Intro'][2]
    if int(main['Alignment']) not in (1, 2, 3) or int(intro['Alignment']) not in (1, 2, 3):
        raise ValueError('Automatic placement requires bottom-aligned K1 and Intro styles')
    size = lambda s: float(s['Fontsize']) * float(s.get('ScaleY', 100)) / 100
    main_top = height - float(main['MarginV']) - size(main)
    protected_top = main_top - 18 * scale
    if 'K1-furigana' in styles:
        ruby = styles['K1-furigana'][2]
        offset = re.search(r'remember\([\"\']furigana_offset[\"\']\s*,\s*(-?[\d.]+)', body)
        ruby_top = main_top - size(ruby) + (float(offset[1]) if offset else 0)
        protected_top = min(protected_top, ruby_top - 11 * scale)
    old_margin = float(intro['MarginV'])
    countdown_padding = max(float(intro['Outline']), 6 * scale)
    new_margin = max(old_margin, math.ceil(height - protected_top + gap + countdown_padding))
    if height - new_margin - size(intro) - countdown_padding < 0:
        raise ValueError('Insufficient space above lyrics; adjust lyric geometry first')
    index, values, _ = styles['Intro']
    values[fields.index('MarginV')] = str(int(new_margin))
    lines[index] = 'Style: ' + ','.join(values)
    report = {'old_margin_v': old_margin, 'new_margin_v': new_margin,
              'protected_effect_top_estimate': protected_top,
              'countdown_bottom_estimate': height - new_margin + countdown_padding,
              'gap': gap, 'changed': new_margin != old_margin,
              'timing_changed': False}
    return '\n'.join(lines) + '\n', report


def fix_file(source: Path, output: Path, gap: float | None = None) -> dict:
    body, report = fix_spacing(source.read_text(encoding='utf-8-sig'), gap)
    temporary = output.with_name(output.name + '.tmp')
    temporary.write_text(body, encoding='utf-8-sig')
    temporary.replace(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, help='defaults to input; in-place edits need --overwrite')
    parser.add_argument('--gap', type=float, help='pixels; default scales 24px at 1080p')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    output = args.output or args.input
    if output.exists() and not args.overwrite and not args.dry_run:
        parser.error('Output exists; use --overwrite or another --output')
    try:
        _, report = fix_spacing(args.input.read_text(encoding='utf-8-sig'), args.gap)
        if not args.dry_run:
            report = fix_file(args.input, output, args.gap)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
