# Auto Clicker 1.0.12: the card says which hotkey it holds

## What
- `%APPDATA%\ProtagonistLabs\apps\autoclicker.json` gains
  `"hotkeys": [{"combo": "F6", "does": "Starts and stops clicking", "registered": true}]`.
  Auto Clicker registers one global hotkey (start/stop), so the list has one entry.
- `combo` is in HotkeyScan's notation: modifiers in its `Combo.ToString` order (Win, Ctrl, Alt,
  Shift) and its key names (`F6`, `Ctrl+Shift+1`, `Win+Alt+PageDown`, `Num7`, `Shift+OEM102`).
  `hotkeyscan_combo`, already used for `HotkeyScan --check`, now emits that order and knows `OEM102`.
- The card is rewritten every time the hotkey is registered (window shown, hotkey changed), when
  registration fails (`registered: false`), and when the window closes and lets the hotkey go
  (`registered: false`). Before, it was written once at start-up from a background thread; that
  write moved into `_register` so the two could not race.
- Works with: "HotkeyScan · knows Auto Clicker's hotkey, and shows which app holds a taken one".

## Why
Plan item 8 (Plan-integrari-ecosistem-2026-10-20): Lume, Frostpane and Auto Clicker are the only
apps of ours that register global hotkeys; with them declared in the cards HotkeyScan 1.1.0 can show
conflicts between our own apps.

## How tested
Function level, scratch `APPDATA` (no window, no hotkey registered; the user's copies were running
from the repo exe): `scratchpad\integ\autoclicker\test_card.py`.
- Run from source: no card written (unchanged rule: it would point sisters at python.exe).
- 6 hotkeys x registered true/false = 12 writes: schema 1, version 1.0.12, exact `hotkeys` entry,
  key name present in HotkeyScan's `Combo.cs` key table, no `.tmp` left. 0.94 ms per write.
- Bad input: `apps` is a file, not a folder: no exception.
- The real card in `%APPDATA%` kept its 06:57 timestamp.
- `python -m PyInstaller --noconfirm autoclicker.spec` built `Auto Clicker.exe` (88,333,188 bytes,
  version resource 1.0.12, Protagonist Labs) into a scratch dist: the repo copy was locked by the
  user's two running instances.

## Untested
- The built exe was not started (it would contend with the running copy for the hotkey), so the
  `_register` / `closeEvent` call sites were checked by reading, not by running.
- A crash leaves `registered: true` behind; readers should treat it as a declaration and confirm
  against the live owner.
- HotkeyScan's reader (1.1.0) does not exist yet.
