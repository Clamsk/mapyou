"""
MapYou - 福州市社区便利度个性化分析
启动器：自动打开浏览器访问本地服务器
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import networkx as nx
from scipy.spatial import KDTree
import folium
from folium.plugins import MarkerCluster, HeatMap
import json
import webbrowser
import threading
import time
import sys
import os

# 获取资源文件路径（打包后的路径处理）
def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容打包后的环境"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        base_path = sys._MEIPASS
    else:
        # 开发环境
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)

app = Flask(__name__,
            template_folder=get_resource_path('templates'),
            static_folder=get_resource_path('static'))

# 数据目录
DATA_DIR = Path(get_resource_path('.'))
CACHE_DIR = DATA_DIR / "输出"

# ... 保持原有的所有代码不变 ...
# （这里会在实际打包时使用完整的服务器代码）

def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # 启动浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    print("="*80)
    print("MapYou - 福州市社区便利度个性化分析系统")
    print("="*80)
    print("\n正在启动服务器...")
    print("浏览器将自动打开，如未打开请手动访问: http://127.0.0.1:5000")
    print("\n关闭此窗口将停止服务\n")
    print("="*80)

    # 启动Flask服务器（生产模式）
    app.run(host='127.0.0.1', port=5000, debug=False)
