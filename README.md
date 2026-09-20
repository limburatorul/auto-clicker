# Auto Clicker

**Download and details:** [protagonistlabs.app/autoclicker](https://protagonistlabs.app/autoclicker/)

A free Windows clicker with a global hotkey, multi-point routes, and scripted
sequences that can wait for something to appear on screen before they act.

- **One click, one hotkey** — an interval down to 1 ms, a global hotkey that
  works from any window, random intervals so a long run doesn't land on the
  same beat every time.
- **Routes** — click a list of saved points in order, not just the cursor.
- **Sequences** — a small step tree: click, move, delay, loop (fixed count or
  until stopped), and conditions.
- **Image detection** — capture a piece of the screen and wait for it to
  reappear before clicking, or branch on whether it's there (OpenCV template
  matching under the hood).
- **Profiles**, and saved/loadable sequences as plain JSON.

Everything above is free. There's no license key and no Pro tier.

## Running from source

```bash
pip install PySide6-Essentials opencv-python numpy
python autoclicker.py
```

Windows only — it talks to `user32`/`gdi32`/`dwmapi` directly through `ctypes`
for input, the global hotkey, acrylic window effects, and screen capture.

## Building the .exe

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name "Auto Clicker" \
  --icon app.ico --add-data "app.ico;." \
  --distpath . --workpath build --specpath build \
  --exclude-module tkinter --exclude-module PIL \
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick \
  --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtOpenGL \
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtDBus \
  autoclicker.py
```

Once a `build/Auto Clicker.spec` exists, `python -m PyInstaller --noconfirm
build/"Auto Clicker.spec" --distpath . --workpath build` rebuilds from it
directly.

## Project layout

| File | What it is |
|---|---|
| `autoclicker.py` | the window, tabs, hotkey capture, profiles |
| `engine.py` | the step model and the thread that runs a sequence |
| `editor.py` | the step dialog, the sequence tree, the screen/image pickers |
| `winapi.py` | everything that talks to Windows directly |
| `store.py` | settings and profiles on disk |
| `theme.py` | the one stylesheet |
| `site/` | the presentation page — `page.template.html` is the source, `build_page.py` inlines `screenshots/` into `site.html` |
