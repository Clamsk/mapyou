# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all jaraco modules
jaraco_datas, jaraco_binaries, jaraco_hiddenimports = collect_all('jaraco')

block_cipher = None

a = Analysis(
    ['交互式便利度地图_服务器.py'],
    pathex=[],
    binaries=jaraco_binaries,
    datas=[
        ('templates', 'templates'),
        ('输出/缓存_路网图.gpickle', '输出'),
        ('输出/缓存_总社区poi.xlsx', '输出'),
        ('输出/缓存_总设施poi.xlsx', '输出'),
        ('输出/缓存_总设施poi_带节点.xlsx', '输出'),
    ] + jaraco_datas,
    hiddenimports=[
        'flask',
        'pandas',
        'numpy',
        'geopandas',
        'networkx',
        'scipy',
        'scipy.spatial',
        'folium',
        'folium.plugins',
        'branca',
        'openpyxl',
        'jinja2',
    ] + jaraco_hiddenimports + collect_submodules('pkg_resources') + collect_submodules('setuptools'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pkg_resources',  # 完全禁用pkg_resources，使用importlib.metadata代替
        'matplotlib',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'tkinter',
        'gtk',
        'wx',
        'PIL.ImageQt',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MapYou-福州社区便利度分析',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)
