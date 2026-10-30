# ASS styles and speakers

Read this reference when editing ASS sizes, colors, titles, speaker fields, or karaoke templates.

ASS colors use BGR order (`#RRGGBB` becomes `&HBBGGRR`). Scale requested styles and furigana counterparts together, rounding practical integer font sizes; for example, 144 at 75% becomes 108, 83 becomes 62, and 69 becomes 52.

For a title, update `[Script Info]` with `Title:` and add a short `Dialogue` event using the existing `Title` style. Keep karaoke timing lines and template comments intact.

## Font, ruby, and countdown spacing

### Approved default: compact serif KTV

The user approved the compact style used for `スタァライト` and `Lessonナweek!!` on 2026-10-30. Use this as the default for future songs unless the user requests another style. These are ASS style units at `PlayResX=1920`, `PlayResY=1080`, not measured glyph heights; scale all geometry proportionally for other script resolutions.

| Setting | Main lyrics (`Default`, `K1`, `K2`) | Ruby (`Default-furigana`, `K1-furigana`, `K2-furigana`) |
| --- | --- | --- |
| Fontname | `Source Han Serif SemiBold` | `Source Han Serif SemiBold` |
| Fontsize | 84 | 34 |
| Bold | -1 | 0 |
| ScaleX / ScaleY | 100 / 100 | 100 / 100 |
| Spacing | 1.2 | 0 |
| Outline | 3.5 | 1.3 |
| Shadow | 0 | 0 |

Use `remember("furigana_offset", -10)`, `top_edge_ratio=0.3`, `bottom_edge_ratio=0.2`, and `reveal_max_lum=150` in the existing template. Preserve its karaoke effects and song-specific speaker colors. Do not replace the font with a rounded font. Check that the exact family is installed and resolves before rendering; if absent, install the matching font or report the missing font rather than silently substituting.

| Row | Alignment | MarginL | MarginR | Standard MarginV | Raised MarginV |
| --- | --- | --- | --- | --- | --- |
| K1 and its ruby | 1 | 84 | 28 | 245 | 300 |
| K2 and its ruby | 3 | 28 | 84 | 70 | 140 |

Use the standard layout for ordinary sources. Use the raised layout when the source already has bottom subtitles, then check their actual bounds. Keep main/ruby row margins synchronized; the template offset controls ruby placement. These margins are layout starting points, not a guarantee against every source caption.

Use the same font for `Intro` with size 50, Bold -1, Spacing 1.2, Outline 3.5, Shadow 0, Alignment 1, MarginL 77 and MarginR 26. Preserve the template's countdown outline override (`\bord6`). Calculate Intro MarginV with `aegisub_cli_template.py result.ass --fix-countdown`; do not copy a previous song's countdown margin. The default visible clearance is 24 at 1080p.

For the opening `Title`, use the same font, size 34, Bold -1, Spacing 1.2, Outline 3.5, Shadow 0, Alignment 7, and margins 26 / 77 / 13. Show it briefly (the approved examples use 0.30–5.50 seconds), with an optional second artist line. Keep this title independent of lyric timing.

Apply these settings after any API operation that rebuilds styles, and before expanding templates. Persist them in the source `result.ass`; changing only `new.ass` is lost on regeneration. Do not enlarge this approved compact preset automatically because older examples used bigger text.

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
