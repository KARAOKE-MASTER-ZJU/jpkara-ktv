# ASS styles and speakers

Read this reference when editing ASS sizes, colors, titles, speaker fields, or karaoke templates.

ASS colors use BGR order (`#RRGGBB` becomes `&HBBGGRR`). Scale requested styles and furigana counterparts together, rounding practical integer font sizes; for example, 144 at 75% becomes 108, 83 becomes 62, and 69 becomes 52.

For a title, update `[Script Info]` with `Title:` and add a short `Dialogue` event using the existing `Title` style. Keep karaoke timing lines and template comments intact.

For ASS editing details, use the [Aegisub Manual](https://aeg-dev.github.io/AegiSite/docs/3.0/Main_Page/), especially [Styles](https://aeg-dev.github.io/AegiSite/docs/3.0/Styles/) and [ASS Tags](https://aeg-dev.github.io/AegiSite/docs/3.0/ASS_Tags/). Use documented syntax for `\\k`, `\\1c`, `\\3c`, `\\pos`, and `\\an`.

For MyGO!!!!!, the commonly used band color is `#3388BB`, represented in ASS as `&HBB8833`; apply it to the relevant accent and karaoke template default while preserving readable white text and outline contrast.

## Speaker / actor mapping

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
