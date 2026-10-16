#!/usr/bin/env python3
"""Apply the 百億年分のしあわせ character split to an aligned ASS."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

CHARAS = {
    1: "日野下花帆", 2: "村野沙耶香", 3: "大泽瑠璃乃", 4: "百生吟子",
    5: "徒町小铃", 6: "安养寺姬芽", 7: "塞拉斯·柳田·利林费尔德", 8: "桂城泉",
}
ALL = ";".join(CHARAS[i] for i in range(1, 9))

# One entry per aligned lyric Dialogue, in the same order as lyrics.txt.
ROLE_NUMBERS = [
    [8], [8], [5], [5], [6], [6], [4], [4], [7], [7],
    list(range(1, 9)), list(range(1, 9)), list(range(1, 9)), list(range(1, 9)),
    list(range(1, 9)), list(range(1, 9)), list(range(1, 9)), [6], [2, 3],
    [1, 7], [4], [8, 5], [3], [3], [1], [1], [2], [2], list(range(1, 9)),
    [2], [2], [3], [3], [1], [1], [1], [1], [1], [1], list(range(1, 9)),
    list(range(1, 9)), [1], [6], [5], [5], list(range(1, 9)),
    list(range(1, 9)), list(range(1, 9)),
]

COLOR_COMMENT = (
    'Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,code once,'
    'remember("default_color", "&H5564F5&"); '
    'remember("color_table", {'
    '["塞拉斯·柳田·利林费尔德"]="&H5564F5&",'
    '["日野下花帆"]="&H00B5F8&",["徒町小铃"]="&H64D7FA&",'
    '["桂城泉"]="&HCDBE1E&",["百生吟子"]="&HDDD7A2&",'
    '["村野沙耶香"]="&HC38353&",["安养寺姬芽"]="&HE28D9D&",'
    '["大泽瑠璃乃"]="&H9E60E7&"});'
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aligned", type=Path)
    parser.add_argument("style_reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ref = args.style_reference.read_text(encoding="utf-8-sig")
    aligned = args.aligned.read_text(encoding="utf-8-sig")
    ref_header = ref.split("[Events]\n", 1)[0] + "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    ref_event_comments = [
        line for line in ref.split("[Events]\n", 1)[1].splitlines()
        if line.startswith("Comment:")
    ]
    dialogues = [line for line in aligned.splitlines() if line.startswith("Dialogue:")]
    if len(dialogues) != len(ROLE_NUMBERS):
        raise SystemExit(f"expected {len(ROLE_NUMBERS)} Dialogue lines, found {len(dialogues)}")
    output = [ref_header, COLOR_COMMENT, *ref_event_comments]
    for line, role_ids in zip(dialogues, ROLE_NUMBERS):
        fields = line.split(",", 9)
        fields[4] = ";".join(CHARAS[i] for i in role_ids)
        output.append(",".join(fields))
    args.output.write_text("\n".join(output) + "\n", encoding="utf-8-sig")
    print(f"wrote {len(dialogues)} speaker-tagged lines to {args.output}")


if __name__ == "__main__":
    main()
