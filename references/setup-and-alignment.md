# Setup and alignment

Read this reference when jpkara/yohane is missing or a new Japanese lyric alignment is required.

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
