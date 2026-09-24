@echo off
chcp 65001 >nul
title POI爬虫工具

:: 设置Qt插件路径
set QT_PLUGIN_PATH=%~dp0.venv\Lib\site-packages\PyQt5\Qt5\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%~dp0.venv\Lib\site-packages\PyQt5\Qt5\plugins\platforms

:: 运行程序
"%~dp0.venv\Scripts\python.exe" "%~dp0poi_crawler_gui.py"

pause
