# ASS styles and speakers

Read this reference when editing ASS sizes, colors, titles, speaker fields, or karaoke templates.

ASS colors use BGR order (`#RRGGBB` becomes `&HBBGGRR`). Scale requested styles and furigana counterparts together, rounding practical integer font sizes; for example, 144 at 75% becomes 108, 83 becomes 62, and 69 becomes 52.

For a title, update `[Script Info]` with `Title:` and add a short `Dialogue` event using the existing `Title` style. Keep karaoke timing lines and template comments intact.

## Font, ruby, and countdown spacing

When reverting a font/style, identify the actual saved version rather than guessing from labels such as “the version before last.” Preserve its main/ruby size ratio, K1/K2 spacing, and margins. A font change can alter glyph metrics even at the same nominal size; check widths and vertical bounds again.

Reserve separate vertical space for upper-row kanji, its ruby, lower-row lyrics/ruby, and the `Intro` countdown (`●●●`). Include outlines, glow, and template offsets in the bounds. A countdown margin copied from another font or row height can put the circles across the first kanji. Move the countdown above the upper ruby with a visible gap, then regenerate the expanded ASS from its source; moving only the already-expanded file leaves the next build broken. Do not copy fixed pixel margins blindly between resolutions.

Use `aegisub_cli_template.py result.ass --fix-countdown` to repair and expand in one command. For inspection or independent editing, run `fix_countdown_spacing.py result.ass --dry-run`, or add `--overwrite` to persist the source edit (`--output` writes a separate source). `--gap` specifies pixels; the default scales 24px at 1080p. The calculation uses PlayResY, K1/ruby sizes and vertical scale, margins, the declared furigana offset, and standard jpkara effect padding. It only increases the Intro margin and is idempotent. This is for bottom-aligned K1/Intro templates; custom absolute positions/effects need their own geometry review. The helper rejects already-expanded ASS and never changes dialogue times or lyrics.

Normally inspect representative rendered frames after layout changes. If the user explicitly requests direct rendering without previews, honor that request, check expanded positions and bounds numerically, and validate the final encode without adding a preview approval step.

For ASS editing details, use the [Aegisub Manual](https://aeg-dev.github.io/AegiSite/docs/3.0/Main_Page/), especially [Styles](https://aeg-dev.github.io/AegiSite/docs/3.0/Styles/) and [ASS Tags](https://aeg-dev.github.io/AegiSite/docs/3.0/ASS_Tags/). Use documented syntax for `\\k`, `\\1c`, `\\3c`, `\\pos`, and `\\an`.

For MyGO!!!!!, the commonly used band color is `#3388BB`, represented in ASS as `&HBB8833`; apply it to the relevant accent and karaoke template default while preserving readable white text and outline contrast.

## Speaker / actor mapping

For remote mapping from Moegirl Wikitext plus an aligned ASS, follow [aegi-api.md](aegi-api.md). Apply that service before final style adjustments: it rebuilds the ASS header and styles. Keep furigana disabled when the existing readings should be retained.

The fifth CSV field of an ASS `Dialogue` event is `Name`, treated by the jpkara/Aegisub template as the speaker or actor. It is not the style name and does not automatically change color:

```text
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:27.18,0:00:28.98,Default,春宮ゆくり,0,0,0,karaoke,{\k6}ね{\k30}ぇ...
```

`color_table` maps the exact `Name` to an ASS BGR color:

```lua
remember("default_color", "&H006CED&")
remember("color_table", {
  ["駒形花火"] = "&H1F21FE&",
  ["調布のりこ"] = "&HFF96CC&",
  ["春宮ゆくり"] = "&HFEF9B1&",
  ["山田真緑"] = "&H00B318&",
})
```

Lookup is `line.actor` → `color_table[line.actor]` → `default_color`. `seg_actor(syl, line)` prefers `syl.inline_fx` and otherwise uses `line.actor`. `find_colors(actors)` accepts semicolon-separated names, so a shared line can use `Name=山田真緑;調布のりこ` with syllable-level `{-山田真緑}` / `{-調布のりこ}` markers.

Keep speaker names byte-for-byte identical between `Name`, inline actor markers, and `color_table` keys. Do not translate names or add spaces. Preserve the original `Name` on karaoke and pass-through lines.
