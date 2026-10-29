# Setup and alignment

Read this reference when jpkara/yohane is missing or a new Japanese lyric alignment is required.

## Reuse installed UVR models before downloading

When UVR is installed, first inspect its configured model directories and any locations the user identified. Under WSL, include the relevant mounted Windows installation; searching only the Linux cache is insufficient. Record the selected model filename, backend, and settings. Prefer existing compatible weights over a fresh download, and do not replace the installed original.

Check the separator's companion metadata before inference. For `audio-separator`, this can include `vr_model_data.json`, `mdx_model_data.json`, model hashes, and model-parameter files. Existing weights alone may still trigger network access if this lookup data is absent. Reuse matching metadata supplied with the installation; a metadata failure is not evidence that the weights need downloading again.

If the separator requires a different directory layout, stage a private working directory with symlinks or copies and the needed metadata. Use a filesystem that supports symlinks; otherwise copy deliberately. Avoid installing dependencies, caches, and credentials into the UVR installation itself. If the audio reader cannot decode a downloaded WebM/Opus file, decode it to PCM WAV first while preserving its time origin, channel layout, and rate.

Run one compatible existing model and validate its outputs before trying alternatives. Confirm both stems cover the intended source interval and assess vocal suppression on sung passages. Delete only this task's failed/partial downloads and disposable staging after success, never the user's original weights or unrelated cache files.

## Portable setup

Do not assume this computer already has either repository. Keep repository URLs public and never hard-code tokens or credentials.

```bash
JPKARA_DIR="${JPKARA_DIR:-$HOME/jpkara}"
YOHANE_DIR="$(dirname "$JPKARA_DIR")/yohane"

command -v git >/dev/null || { echo "git is required"; exit 1; }
if [ ! -d "$JPKARA_DIR/.git" ]; then
  git clone https://github.com/KARAOKE-MASTER-ZJU/hinana.git "$JPKARA_DIR"
fi

if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if [ ! -x "$YOHANE_DIR/.venv/bin/python" ] || [ ! -f "$YOHANE_DIR/run.py" ]; then
  bash "$JPKARA_DIR/setup.sh"
fi
```

The setup script clones yohane beside jpkara, creates its virtual environment with `uv sync --extra cli`, and installs jpkara plus MeCab dependencies into the same environment. Preserve existing checkout changes; do not delete or reset them. If setup fails because network, disk, GPU, or permissions are unavailable, report the concrete blocker and stop before producing a falsely aligned result.

Verify before running a song:

```bash
test -f "$YOHANE_DIR/run.py"
test -x "$YOHANE_DIR/.venv/bin/python"
PYTHONPATH="$JPKARA_DIR" "$YOHANE_DIR/.venv/bin/python" -m jpkara.cli --help >/dev/null
ffmpeg -version >/dev/null
```

If GPU encoding is requested, check `ffmpeg -hide_banner -encoders` for `h264_nvenc`; state any software fallback.

## Run alignment

```bash
PYTHONPATH="$JPKARA_DIR" "$YOHANE_DIR/.venv/bin/python" -m jpkara.cli \
  SONG.mp4 lyrics.txt --mode furigana -o output.ass \
  --yohane-dir "$YOHANE_DIR"
```

Use a vocals stem as the alignment input when one exists, but keep the full mix for the final on-vocal video. If the remote LLM reading service fails, use `--no-llm`; local kana conversion plus yohane alignment is an acceptable fallback. Confirm the expected number of karaoke `Dialogue` lines and no temporary ASS remains.

## FA-Kara alignment-only path

`FA-Kara` is an alternative forced-alignment tool, not a reading/furigana engine. Its repository is [moriwx/FA-Kara](https://github.com/moriwx/FA-Kara). It expects:

- vocals-only audio (the repository README uses `i.wav`; `main.py` also accepts an explicit audio path such as `1_input_(Vocals).mp3`), and
- one lyric line per line using its furigana syntax, e.g. `{避|よ}けた`.

Annotate kanji runs only. Never wrap a whole mixed kanji/okurigana token: use `{終|お}わって`, not `{終わって|おわって}`, and `{見|み}つけ{出|だ}して`, not `{見つけ出して|みつけだして}`. Whole-token annotation duplicates visible okurigana in Aegisub ruby. `yohane_readings_to_fa.py` enforces this for new input; run `normalize_fa_lyrics.py` on legacy FA-Kara input before alignment.

When the user selects FA-Kara, derive that reading text from the already annotated ASS (or another user-approved reading source). Do not rerun LLM/pykakasi/RhythmicaLyrics reading analysis as part of the FA-Kara step. Run it from its checkout, typically:

```bash
CUDA_VISIBLE_DEVICES='' "$YOHANE_DIR/.venv/bin/python" "$HOME/FA-Kara/main.py" \
  -p "$HOME/FA-Kara" \
  -ia "/path/to/vocals.mp3" \
  -it annotated_lyrics.txt
```

The command writes FA-Kara's native `o.ass` and auxiliary LRC files in its working directory. Apply post-processing in this order:

1. Before alignment, run `normalize_fa_lyrics.py` so `{終わって|おわって}` becomes `{終|お}わって` and visible okurigana is not repeated as ruby.
2. Run FA-Kara on the normalized reading text and vocals-only audio.
3. Run `normalize_furigana_ass.py` so bare continuation markers `#|reading` become Aegisub/jpkara `#|<reading`.
4. Run `fix_okurigana_ass.py` on the aligned ASS. This is a safety pass for mixed Japanese tokens that survived input normalization; it must preserve karaoke timing while leaving only the kanji reading above the kanji. Preserve intentional Latin/French surface text and its pronunciation annotation from the normalized ASS if a Japanese-only cleanup helper would replace it with kana. Compare visible lyrics before and after cleanup.
5. Only then apply styles, speakers, colors, titles, or Aegisub karaoke templates. Do not flatten/remove furigana when the requested deliverable needs readings.

Validate the dialogue count, visible lyrics, readings, empty Actor fields when no speaker mapping was requested, and absence of duplicated okurigana such as `終わって|<お ... #|<わっ ... #|<て`. Then copy/rename the ASS only after validation. FA-Kara's native style is not jpkara's template style; if the user requires jpkara styles, apply them as a separate post-processing step without changing alignment timings. Force CPU with `CUDA_VISIBLE_DEVICES=''` when a small GPU may OOM, and report that FA-Kara is alignment-only if the user asks about its capabilities.

For noisy live recordings or dense harmony, prefer the isolated vocals for alignment and review suspicious long tails over instrumental gaps. Burned-in lyrics may appear before singing starts; their appearance times are not acoustic ground truth. If a short response, foreign-language phrase, or ending is misaligned, rerun only a bounded vocals crop and add its crop offset back exactly once. Keep separately sung responses in separate events when needed; avoid shifting an otherwise valid whole song to repair one phrase.

## Reusable helpers

The skill ships wrappers under `scripts/`:

```bash
python scripts/split_lyrics.py lyrics.raw.txt lyrics.txt --max-chars 15
python scripts/yohane_readings_to_fa.py lyrics.txt fa_lyrics.txt --jpkara-dir "$JPKARA_DIR"
python scripts/ass_to_fa_lyrics.py existing.ass fa_lyrics.txt
python scripts/normalize_fa_lyrics.py fa_lyrics.txt fa_lyrics.fixed.txt
python scripts/run_fa_kara.py --audio vocals.wav --lyrics fa_lyrics.fixed.txt \
  --output result_aligned.raw.ass --python "$YOHANE_DIR/.venv/bin/python"
python scripts/normalize_furigana_ass.py result_aligned.raw.ass result_aligned.normalized.ass
python scripts/fix_okurigana_ass.py result_aligned.normalized.ass result_aligned.ass
```

The splitter keeps ASCII words intact but needs a human phrasing review. Prepare readings with either the YOHANE helper or `ass_to_fa_lyrics.py`; normalize every generated or legacy FA input before alignment so okurigana is not duplicated as ruby. Then use `run_fa_kara.py` for alignment only and apply both ASS normalization passes in the shown order. The wrapper defaults to CPU; pass `--gpu` only after checking available VRAM.
