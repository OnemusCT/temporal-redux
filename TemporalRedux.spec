# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller TemporalRedux.spec
#
# Produces a single-file, windowed (no console) executable.
# On Windows: dist/TemporalRedux.exe
# On macOS:   dist/TemporalRedux.app (onefile binary wrapped in an app bundle)

import os
import sys

SOURCE_DIR = os.path.join(SPECPATH, 'sourcefiles')

a = Analysis(
    [os.path.join(SOURCE_DIR, 'temporalredux.py')],
    pathex=[SOURCE_DIR],
    binaries=[],
    datas=[
        # ctstrings.py loads huffman_table.pickle relative to its own
        # __file__ at import time; PyInstaller's static analysis can't see
        # this since it isn't an import statement, so it must be listed here.
        # The codebase imports jetsoftime both as a top-level package
        # ("jetsoftime.x") and as "sourcefiles.jetsoftime.x", which load as
        # two distinct frozen modules at two different bundle paths, so the
        # data has to be duplicated at both locations.
        (os.path.join(SOURCE_DIR, 'jetsoftime', 'pickles'), 'jetsoftime/pickles'),
        (os.path.join(SOURCE_DIR, 'jetsoftime', 'pickles'), 'sourcefiles/jetsoftime/pickles'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    # macOS: onefile binaries can't be wrapped in a .app bundle, so build
    # onedir and collect it into TemporalRedux.app instead.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='TemporalRedux',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='TemporalRedux',
    )
    app = BUNDLE(
        coll,
        name='TemporalRedux.app',
        icon=None,
        bundle_identifier='org.ctjot.temporalredux',
    )
else:
    # Windows: a single portable executable.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='TemporalRedux',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
