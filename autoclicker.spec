# -*- mode: python ; coding: utf-8 -*-
# Builds "Auto Clicker.exe":  .venv\Scripts\python -m PyInstaller --noconfirm autoclicker.spec --distpath . --workpath build
# (.venv holds a PyInstaller whose bootloader was compiled here from source: see README, Building the .exe.)
import re
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

# The one version number lives in autoclicker.py (the updater compares it); the exe's version resource follows it.
VERSION = re.search(r'^VERSION = "([\d.]+)"', open(SPECPATH + '/autoclicker.py', encoding='utf-8').read(), re.M).group(1)
NUMS = tuple(int(n) for n in VERSION.split('.')) + (0,)

# Who made it and what it is: an exe that says neither is what antivirus heuristics flag first.
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMS, prodvers=NUMS),
    kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'Protagonist Labs'),
        StringStruct('FileDescription', 'Auto Clicker'),
        StringStruct('FileVersion', VERSION),
        StringStruct('InternalName', 'Auto Clicker'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 Protagonist Labs. GPL-3.0 licence'),
        StringStruct('OriginalFilename', 'Auto Clicker.exe'),
        StringStruct('ProductName', 'Auto Clicker'),
        StringStruct('ProductVersion', VERSION)])]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])])])

a = Analysis(
    ['autoclicker.py'],
    datas=[('app.ico', '.')],
    excludes=['tkinter', 'PIL', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtOpenGL',
              'PySide6.QtNetwork', 'PySide6.QtDBus'],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Auto Clicker',
    upx=False,  # packed DLLs look like malware to scanners; Auto Clicker ships them as they are
    console=False,
    icon=[SPECPATH + '/app.ico'],
    version=version,
)
