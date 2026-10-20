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
.venv/Scripts/python -m PyInstaller --noconfirm autoclicker.spec --distpath . --workpath build
```

`autoclicker.spec` takes the version from `VERSION` in `autoclicker.py` and writes it, with
Protagonist Labs as the company, into the exe's version resource. It never packs with UPX.

`.venv` is a build environment whose PyInstaller has a bootloader compiled here from source,
not the prebuilt one every PyInstaller app shares (antivirus engines learn that one from
malware built with it). To set it up once (Python 3.11, PySide6 installed, MSVC build tools):

```bash
python -m venv --system-site-packages .venv
.venv/Scripts/python -m pip download pyinstaller==6.20.0 --no-binary :all: --no-deps -d .venv/src
tar xzf .venv/src/pyinstaller-6.20.0.tar.gz -C .venv/src
cd .venv/src/pyinstaller-6.20.0/bootloader && ../../../Scripts/python ./waf all --target-arch=64bit
cd .. && ../../Scripts/python -m pip install --no-deps .
```

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

## More from Protagonist Labs

- [HotkeyScan](https://protagonistlabs.app/hotkeyscan/?utm_source=github&utm_medium=readme&utm_campaign=autoclicker): finds which program already holds a hotkey, free. Auto Clicker lists its own hotkey,
  and whether it holds it right now, in its card under `%APPDATA%\ProtagonistLabspps\`, so HotkeyScan
  can tell when two of our apps want the same keys.
- [Shelf](https://protagonistlabs.app/shelf/?utm_source=github&utm_medium=readme&utm_campaign=autoclicker): every PC game from every launcher in one library.
- [All apps](https://protagonistlabs.app/?utm_source=github&utm_medium=readme&utm_campaign=autoclicker): Windows apps that each do one job properly.
