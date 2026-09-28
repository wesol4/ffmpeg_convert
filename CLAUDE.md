# FFmpeg Convert

Desktop media utility: Python 3.12, PyQt5, FFmpeg/ffprobe. UI text is Polish.
Preserve the existing compact desktop layout; do not replace it with a web UI.

## Architecture

- `app/core/sequences.py`: read-only discovery of frame sequences and matching audio.
- `app/presets/`: shared conversion recipes for GUI and CLI; return `Job` objects.
- `app/runner.py`: execute argument arrays, report progress, clean temporary resources.
- `app/gui_panels.py`, `app/gui_main_window.py`: user choices and presentation.
- `app/audio_separation.py`: optional isolated CPU model; never upload user media.

## Working on conversion scenarios

Keep GUI and CLI behavior consistent. Test actual FFmpeg output, not only command
strings, when changing stream selection, frame count, duration or codecs.

For numbered frames, detect only the selected sequence in its immediate folder.
Show the count/range before switching from image conversion to video. Do not
silently mix sequences or close gaps. Keep single-image conversion available.
Audio is explicit or matched by sequence/folder name. Ambiguity requires choosing
a file. Pad shorter audio with silence and trim longer audio to the video duration.
Never use the output file as an input or silently replace an existing sequence video.

Use subprocess argument lists without a shell. Escape filenames in FFmpeg concat
lists; reject newlines. Treat filenames as plain text in Qt labels. Verify the
fixed model checksum before deserialization. Clean only temporary paths created
by the current job. Do not commit model/runtime files or user media.

## Validation

```sh
venv/bin/ruff check .
venv/bin/mypy app
venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_gui_sequences.py -v
```

The last command needs PyQt5 in the chosen interpreter. Review the window at a
normal desktop size after layout changes. Keep controls keyboard-accessible and
put sequence count, duration, audio selection and action near each other.

## Guidance used

This project guidance applies the relevant parts of Anthropic's
[claude-code-setup](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/claude-code-setup),
[frontend-design](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design)
and [security-guidance](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance).
It does not install or enable Claude hooks, external reviewers or paid API calls.
