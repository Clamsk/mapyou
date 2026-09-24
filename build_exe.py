#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
打包脚本 - 将POI爬虫打包成独立exe
"""

import PyInstaller.__main__
import os
import shutil

# 当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 主程序文件
main_script = os.path.join(current_dir, 'poi_crawler_gui.py')

# 打包参数
args = [
    main_script,
    '--name=百度地图POI爬虫',
    '--onefile',                    # 打包成单个exe文件
    '--windowed',                   # 不显示控制台窗口
    '--noconfirm',                  # 覆盖输出目录
    '--clean',                      # 清理临时文件
    f'--distpath={os.path.join(current_dir, "dist")}',
    f'--workpath={os.path.join(current_dir, "build")}',
    f'--specpath={current_dir}',
    '--hidden-import=shapely',
    '--hidden-import=shapely.geometry',
    '--hidden-import=pandas',
    '--hidden-import=openpyxl',
    '--hidden-import=requests',
    '--collect-all=shapely',        # 收集shapely所有依赖
]

print("=" * 50)
print("开始打包 百度地图POI爬虫...")
print("=" * 50)

# 执行打包
PyInstaller.__main__.run(args)

print("\n" + "=" * 50)
print("打包完成！")
print(f"输出文件: {os.path.join(current_dir, 'dist', '百度地图POI爬虫.exe')}")
print("=" * 50)
