#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
百度地图POI爬虫 - GUI版本
支持：自定义区域、进度保存、暂停继续、断点续爬
"""

import sys
import os

# 修复PyQt5插件路径问题 - 必须在导入PyQt5之前设置
def setup_pyqt5_path():
    try:
        import PyQt5
        pyqt5_path = os.path.dirname(PyQt5.__file__)

        # 尝试多种可能的路径
        possible_paths = [
            os.path.join(pyqt5_path, 'Qt5', 'plugins'),
            os.path.join(pyqt5_path, 'Qt', 'plugins'),
            os.path.join(pyqt5_path, 'plugins'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                os.environ['QT_PLUGIN_PATH'] = path
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(path, 'platforms')
                break
    except:
        pass

setup_pyqt5_path()

import json
import time
import random
import math
import re
import threading
import difflib
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QGroupBox, QCheckBox, QGridLayout, QMessageBox, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QScrollArea, QLineEdit, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QColor

import requests
from shapely.geometry import shape, Point, MultiPolygon, Polygon
from shapely.ops import unary_union
import pandas as pd


# ==================== 城市代码映射表 ====================
# 百度地图城市代码（常用城市）
CITY_CODES = {
    # 直辖市
    "北京": "131", "北京市": "131",
    "上海": "289", "上海市": "289",
    "天津": "332", "天津市": "332",
    "重庆": "132", "重庆市": "132",
    # 福建省
    "福州": "268", "福州市": "268",
    "厦门": "269", "厦门市": "269",
    "泉州": "270", "泉州市": "270",
    "漳州": "271", "漳州市": "271",
    "莆田": "272", "莆田市": "272",
    "龙岩": "273", "龙岩市": "273",
    "三明": "274", "三明市": "274",
    "南平": "275", "南平市": "275",
    "宁德": "276", "宁德市": "276",
    # 广东省
    "广州": "257", "广州市": "257",
    "深圳": "340", "深圳市": "340",
    "东莞": "256", "东莞市": "256",
    "佛山": "258", "佛山市": "258",
    "珠海": "259", "珠海市": "259",
    "惠州": "260", "惠州市": "260",
    "中山": "261", "中山市": "261",
    # 浙江省
    "杭州": "179", "杭州市": "179",
    "宁波": "180", "宁波市": "180",
    "温州": "181", "温州市": "181",
    "嘉兴": "182", "嘉兴市": "182",
    "绍兴": "183", "绍兴市": "183",
    "金华": "184", "金华市": "184",
    "台州": "185", "台州市": "185",
    # 江苏省
    "南京": "315", "南京市": "315",
    "苏州": "224", "苏州市": "224",
    "无锡": "225", "无锡市": "225",
    "常州": "226", "常州市": "226",
    "南通": "227", "南通市": "227",
    "扬州": "228", "扬州市": "228",
    "镇江": "229", "镇江市": "229",
    # 山东省
    "济南": "288", "济南市": "288",
    "青岛": "236", "青岛市": "236",
    "烟台": "237", "烟台市": "237",
    "威海": "238", "威海市": "238",
    "潍坊": "239", "潍坊市": "239",
    # 四川省
    "成都": "75", "成都市": "75",
    "绵阳": "76", "绵阳市": "76",
    "德阳": "77", "德阳市": "77",
    # 湖北省
    "武汉": "218", "武汉市": "218",
    "宜昌": "219", "宜昌市": "219",
    # 湖南省
    "长沙": "158", "长沙市": "158",
    "株洲": "159", "株洲市": "159",
    # 河南省
    "郑州": "268", "郑州市": "268",
    "洛阳": "379", "洛阳市": "379",
    # 河北省
    "石家庄": "186", "石家庄市": "186",
    "唐山": "187", "唐山市": "187",
    # 陕西省
    "西安": "233", "西安市": "233",
    # 辽宁省
    "沈阳": "58", "沈阳市": "58",
    "大连": "59", "大连市": "59",
    # 吉林省
    "长春": "53", "长春市": "53",
    # 黑龙江省
    "哈尔滨": "56", "哈尔滨市": "56",
    # 安徽省
    "合肥": "127", "合肥市": "127",
    # 江西省
    "南昌": "163", "南昌市": "163",
    # 广西
    "南宁": "261", "南宁市": "261",
    # 云南省
    "昆明": "104", "昆明市": "104",
    # 贵州省
    "贵阳": "146", "贵阳市": "146",
    # 甘肃省
    "兰州": "94", "兰州市": "94",
    # 海南省
    "海口": "125", "海口市": "125",
    "三亚": "126", "三亚市": "126",
}

# 区县到城市的映射（用于区级匹配）
DISTRICT_TO_CITY = {
    # 福州市各区县
    "鼓楼区": "福州", "台江区": "福州", "仓山区": "福州", "马尾区": "福州",
    "晋安区": "福州", "长乐区": "福州", "福清区": "福州",
    "闽侯县": "福州", "连江县": "福州", "罗源县": "福州",
    "闽清县": "福州", "永泰县": "福州", "平潭县": "福州",
    # 厦门市各区
    "思明区": "厦门", "湖里区": "厦门", "集美区": "厦门",
    "海沧区": "厦门", "同安区": "厦门", "翔安区": "厦门",
    # 北京市各区
    "东城区": "北京", "西城区": "北京", "朝阳区": "北京",
    "海淀区": "北京", "丰台区": "北京", "石景山区": "北京",
    # 上海市各区
    "浦东新区": "上海", "黄浦区": "上海", "徐汇区": "上海",
    "长宁区": "上海", "静安区": "上海", "普陀区": "上海",
    # 广州市各区
    "越秀区": "广州", "荔湾区": "广州", "海珠区": "广州",
    "天河区": "广州", "白云区": "广州", "番禺区": "广州",
    # 深圳市各区
    "罗湖区": "深圳", "福田区": "深圳", "南山区": "深圳",
    "宝安区": "深圳", "龙岗区": "深圳", "龙华区": "深圳",
}


def get_city_code(region_name):
    """根据区域名称获取城市代码"""
    # 直接匹配城市
    if region_name in CITY_CODES:
        return CITY_CODES[region_name]

    # 区县匹配 - 先查找区县对应的城市
    if region_name in DISTRICT_TO_CITY:
        city = DISTRICT_TO_CITY[region_name]
        return CITY_CODES.get(city, "1")

    # 左侧子串匹配（如"福州市仓山区" -> "福州"）
    for city, code in CITY_CODES.items():
        if region_name.startswith(city):
            return code

    # 包含匹配
    for city, code in CITY_CODES.items():
        if city in region_name:
            return code

    # 默认返回全国搜索
    return "1"


# ==================== 坐标转换模块 ====================
X_PI = 3.14159265358979324 * 3000.0 / 180.0
PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323


def bd09_to_gcj02(bd_lng, bd_lat):
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def gcj02_to_wgs84(gcj_lng, gcj_lat):
    if not (73.66 < gcj_lng < 135.05 and 3.86 < gcj_lat < 53.55):
        return gcj_lng, gcj_lat
    dlat = transform_lat(gcj_lng - 105.0, gcj_lat - 35.0)
    dlng = transform_lng(gcj_lng - 105.0, gcj_lat - 35.0)
    radlat = gcj_lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return gcj_lng - dlng, gcj_lat - dlat


def bd09_to_wgs84(bd_lng, bd_lat):
    gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def wgs84_to_gcj02(wgs_lng, wgs_lat):
    """WGS-84 转 GCJ-02"""
    if not (73.66 < wgs_lng < 135.05 and 3.86 < wgs_lat < 53.55):
        return wgs_lng, wgs_lat
    dlat = transform_lat(wgs_lng - 105.0, wgs_lat - 35.0)
    dlng = transform_lng(wgs_lng - 105.0, wgs_lat - 35.0)
    radlat = wgs_lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return wgs_lng + dlng, wgs_lat + dlat


def gcj02_to_bd09(gcj_lng, gcj_lat):
    """GCJ-02 转 BD-09"""
    z = math.sqrt(gcj_lng * gcj_lng + gcj_lat * gcj_lat) + 0.00002 * math.sin(gcj_lat * X_PI)
    theta = math.atan2(gcj_lat, gcj_lng) + 0.000003 * math.cos(gcj_lng * X_PI)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def wgs84_to_bd09(wgs_lng, wgs_lat):
    """WGS-84 转 BD-09"""
    gcj_lng, gcj_lat = wgs84_to_gcj02(wgs_lng, wgs_lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


# ==================== 默认POI类别 ====================
DEFAULT_POI_CATEGORIES = {
    "餐饮设施": ["餐厅", "饭店", "快餐", "小吃", "面馆", "火锅", "烧烤", "甜品", "咖啡", "奶茶", "蛋糕店"],
    "超市商场": ["超市", "商场", "便利店", "购物中心", "百货", "菜市场", "水果店"],
    "医疗设施": ["医院", "诊所", "卫生院", "药店", "药房", "社区卫生"],
    "教育设施": ["幼儿园", "小学", "中学", "大学", "学校", "培训机构"],
    "公园广场": ["公园", "广场", "绿地", "游园", "花园"],
    "交通设施": ["地铁站", "公交站", "停车场", "加油站"],
    "金融设施": ["银行", "ATM", "信用社", "证券"],
    "休闲娱乐设施": ["电影院", "KTV", "健身房", "体育馆", "游泳馆", "网吧"]
}


# ==================== 新增类别对话框 ====================
class AddCategoryDialog(QDialog):
    """新增POI类别对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("新增POI类别")
        self.setMinimumSize(400, 350)

        layout = QVBoxLayout(self)

        # 类别名称
        name_layout = QHBoxLayout()
        name_label = QLabel("类别名称:")
        name_label.setFixedWidth(70)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 体育设施")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # 关键词说明
        hint_label = QLabel("搜索关键词（每行一个）:")
        layout.addWidget(hint_label)

        # 关键词文本框
        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlaceholderText("输入关键词，每行一个...\n例如:\n体育馆\n运动场\n健身中心")
        layout.addWidget(self.keywords_edit)

        # 提示
        tip_label = QLabel("提示: 关键词越具体，搜索结果越精准")
        tip_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(tip_label)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def validate_and_accept(self):
        """验证并接受"""
        name = self.name_input.text().strip()
        keywords = self.get_keywords()

        if not name:
            QMessageBox.warning(self, "警告", "请输入类别名称！")
            return
        if not keywords:
            QMessageBox.warning(self, "警告", "请输入至少一个关键词！")
            return

        self.accept()

    def get_category_name(self):
        """获取类别名称"""
        return self.name_input.text().strip()

    def get_keywords(self):
        """获取关键词列表"""
        text = self.keywords_edit.toPlainText()
        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        return keywords


# ==================== 关键词编辑对话框 ====================
class KeywordsEditDialog(QDialog):
    """关键词编辑对话框"""

    def __init__(self, category_name, keywords, parent=None):
        super().__init__(parent)
        self.category_name = category_name
        self.keywords = keywords
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"编辑关键词 - {self.category_name}")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)

        # 说明文字
        hint_label = QLabel("每行一个关键词，空行将被忽略：")
        layout.addWidget(hint_label)

        # 文本编辑框
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText("\n".join(self.keywords))
        self.text_edit.setPlaceholderText("输入关键词，每行一个...")
        layout.addWidget(self.text_edit)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_keywords(self):
        """获取编辑后的关键词列表"""
        text = self.text_edit.toPlainText()
        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        return keywords


# ==================== 爬虫工作线程 ====================
class CrawlerWorker(QThread):
    """爬虫工作线程"""

    # 信号定义
    progress_updated = pyqtSignal(int, int, str)  # 当前进度, 总数, 消息
    log_message = pyqtSignal(str, str)  # 消息, 级别(info/success/warning/error)
    poi_found = pyqtSignal(dict)  # 找到的POI
    category_finished = pyqtSignal(str, int)  # 类别名, 数量
    crawl_finished = pyqtSignal(bool, str)  # 是否成功, 消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = requests.Session()
        self.boundary = None
        self.bounds = None  # 边界范围
        self.categories = {}
        self.region_name = "福州市"
        self.city_code = "268"  # 默认福州

        # 控制标志
        self.is_running = False
        self.is_paused = False
        self.should_stop = False

        # 进度状态（用于断点续爬）
        self.progress_state = {
            'current_category_index': 0,
            'current_keyword_index': 0,
            'current_page': 0,
            'collected_uids': set(),
            'results': [],
            'category_counts': {}
        }

        # 延迟设置
        self.min_delay = 1.5
        self.max_delay = 3.0
        self.retry_delay = 5.0
        self.max_retries = 3

        # 代理设置
        self.use_proxy = False
        self.proxy_url = None

        # 请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://map.baidu.com/',
        }
        self.session.headers.update(self.headers)

    def load_geojson(self, geojson_path):
        """加载GeoJSON边界（自动检测编码）"""
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin-1']
            geojson_data = None
            used_encoding = None

            for encoding in encodings:
                try:
                    with open(geojson_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        geojson_data = json.loads(content)
                        used_encoding = encoding
                        break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

            if geojson_data is None:
                return False, "无法解析文件，请检查文件格式和编码"

            polygons = []
            for feature in geojson_data.get('features', []):
                geom = shape(feature['geometry'])
                if isinstance(geom, MultiPolygon):
                    for poly in geom.geoms:
                        polygons.append(poly)
                else:
                    polygons.append(geom)

            self.boundary = unary_union(polygons)
            self.bounds = self.boundary.bounds  # (minx, miny, maxx, maxy)

            # 尝试获取区域名称
            if geojson_data.get('features'):
                first_feature = geojson_data['features'][0]
                props = first_feature.get('properties', {})
                # 尝试多个可能的名称字段
                name = props.get('name', '') or props.get('NAME', '') or props.get('名称', '') or props.get('CNAME', '')
                if name:
                    self.region_name = name

            # 自动识别城市代码
            self.city_code = get_city_code(self.region_name)

            return True, f"边界加载成功！编码:{used_encoding} 范围: 经度[{self.bounds[0]:.4f}, {self.bounds[2]:.4f}], 纬度[{self.bounds[1]:.4f}, {self.bounds[3]:.4f}]"

        except Exception as e:
            return False, f"加载GeoJSON失败: {str(e)}"

    def load_shapefile(self, shp_path):
        """加载Shapefile边界"""
        try:
            import struct

            # 读取.shp文件
            polygons = []
            with open(shp_path, 'rb') as f:
                # 读取文件头
                f.read(24)  # 跳过文件代码等
                f.read(4)   # 文件长度
                f.read(4)   # 版本
                shape_type = struct.unpack('<i', f.read(4))[0]

                # 读取边界框
                xmin = struct.unpack('<d', f.read(8))[0]
                ymin = struct.unpack('<d', f.read(8))[0]
                xmax = struct.unpack('<d', f.read(8))[0]
                ymax = struct.unpack('<d', f.read(8))[0]
                f.read(32)  # 跳过Z和M范围

                # 读取记录
                while True:
                    try:
                        record_header = f.read(8)
                        if len(record_header) < 8:
                            break

                        record_num, content_len = struct.unpack('>ii', record_header)
                        shape_type_record = struct.unpack('<i', f.read(4))[0]

                        if shape_type_record == 0:  # Null shape
                            continue
                        elif shape_type_record in [5, 15, 25]:  # Polygon, PolygonZ, PolygonM
                            # 读取边界框
                            f.read(32)

                            num_parts = struct.unpack('<i', f.read(4))[0]
                            num_points = struct.unpack('<i', f.read(4))[0]

                            # 读取parts索引
                            parts = [struct.unpack('<i', f.read(4))[0] for _ in range(num_parts)]
                            parts.append(num_points)

                            # 读取点
                            points = []
                            for _ in range(num_points):
                                x = struct.unpack('<d', f.read(8))[0]
                                y = struct.unpack('<d', f.read(8))[0]
                                points.append((x, y))

                            # 构建多边形
                            for i in range(num_parts):
                                ring = points[parts[i]:parts[i+1]]
                                if len(ring) >= 3:
                                    try:
                                        poly = Polygon(ring)
                                        if poly.is_valid:
                                            polygons.append(poly)
                                    except:
                                        pass

                            # 跳过Z或M值
                            if shape_type_record in [15, 25]:
                                remaining = content_len * 2 - 44 - num_parts * 4 - num_points * 16
                                if remaining > 0:
                                    f.read(remaining)
                        else:
                            # 跳过其他类型
                            f.read(content_len * 2 - 4)
                    except:
                        break

            if not polygons:
                return False, "未能从Shapefile中读取有效的多边形"

            self.boundary = unary_union(polygons)
            self.bounds = self.boundary.bounds

            # 尝试从.dbf文件读取属性
            dbf_path = shp_path.replace('.shp', '.dbf').replace('.SHP', '.DBF')
            if os.path.exists(dbf_path):
                try:
                    name = self._read_dbf_name(dbf_path)
                    if name:
                        self.region_name = name
                except:
                    pass

            # 自动识别城市代码
            self.city_code = get_city_code(self.region_name)

            return True, f"Shapefile加载成功！范围: 经度[{self.bounds[0]:.4f}, {self.bounds[2]:.4f}], 纬度[{self.bounds[1]:.4f}, {self.bounds[3]:.4f}]"

        except Exception as e:
            return False, f"加载Shapefile失败: {str(e)}"

    def _read_dbf_name(self, dbf_path):
        """从DBF文件读取名称字段"""
        try:
            with open(dbf_path, 'rb') as f:
                import struct

                # 读取DBF头
                f.read(4)  # 版本和日期
                num_records = struct.unpack('<I', f.read(4))[0]
                header_size = struct.unpack('<H', f.read(2))[0]
                record_size = struct.unpack('<H', f.read(2))[0]
                f.read(20)  # 跳过其他头信息

                # 读取字段描述
                fields = []
                while True:
                    field_desc = f.read(32)
                    if field_desc[0] == 0x0D:
                        break
                    field_name = field_desc[:11].split(b'\x00')[0].decode('gbk', errors='ignore').strip()
                    field_type = chr(field_desc[11])
                    field_len = field_desc[16]
                    fields.append((field_name, field_type, field_len))

                # 找名称字段
                name_fields = ['NAME', 'name', 'CNAME', '名称', 'FNAME', '区县名']
                name_idx = -1
                name_offset = 1  # 第一个字节是删除标记

                for i, (fname, ftype, flen) in enumerate(fields):
                    if fname.upper() in [nf.upper() for nf in name_fields]:
                        name_idx = i
                        break
                    name_offset += flen

                if name_idx >= 0:
                    # 读取第一条记录的名称
                    f.seek(header_size)
                    f.read(name_offset)
                    name_len = fields[name_idx][2]
                    name_data = f.read(name_len)
                    try:
                        name = name_data.decode('gbk').strip()
                    except:
                        name = name_data.decode('utf-8', errors='ignore').strip()
                    return name

        except Exception as e:
            pass
        return None

    def load_boundary_file(self, file_path):
        """加载边界文件（自动识别格式）"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.shp':
            return self.load_shapefile(file_path)
        elif ext in ['.geojson', '.json']:
            return self.load_geojson(file_path)
        else:
            return False, f"不支持的文件格式: {ext}"

    def is_in_boundary(self, lng, lat):
        """判断点是否在边界内"""
        if self.boundary is None:
            return True
        point = Point(lng, lat)
        return self.boundary.contains(point)

    def is_valid_coordinate(self, lng, lat):
        """检查坐标是否有效（BD-09坐标系）"""
        # 基本有效性检查
        if lng is None or lat is None:
            return False, "坐标为空"

        try:
            lng = float(lng)
            lat = float(lat)
        except (TypeError, ValueError):
            return False, "坐标格式错误"

        # 检查是否为0或负数
        if lng <= 0 or lat <= 0:
            return False, "坐标为0或负数"

        # 中国BD-09坐标范围（放宽范围）
        if not (70.0 < lng < 140.0 and 0.0 < lat < 60.0):
            return False, f"坐标超出范围({lng:.2f},{lat:.2f})"

        # 检查经纬度是否完全相同（异常数据）
        if abs(lng - lat) < 0.0001:
            return False, "经纬度相同"

        return True, "OK"

    def calculate_similarity(self, str1, str2):
        """计算两个字符串的相似度"""
        if not str1 or not str2:
            return 0.0
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    def is_duplicate(self, new_poi, existing_results, threshold=0.85):
        """智能判断是否为重复数据

        Args:
            new_poi: 新的POI数据
            existing_results: 已有的结果列表
            threshold: 相似度阈值，默认0.85

        Returns:
            (is_dup, reason): 是否重复，原因
        """
        new_name = new_poi.get('name', '') or new_poi.get('名称', '')
        new_addr = new_poi.get('address', '') or new_poi.get('地址', '')
        new_lng = new_poi.get('lng', 0) or new_poi.get('经度_BD09', 0)
        new_lat = new_poi.get('lat', 0) or new_poi.get('纬度_BD09', 0)

        for existing in existing_results:
            exist_name = existing.get('名称', '')
            exist_addr = existing.get('地址', '')
            exist_lng = existing.get('经度_BD09', 0)
            exist_lat = existing.get('纬度_BD09', 0)

            # 1. 名称完全相同
            if new_name and new_name == exist_name:
                # 同名同地址
                if new_addr and new_addr == exist_addr:
                    return True, "名称+地址完全重复"
                # 同名且坐标非常接近（<50米）
                if abs(new_lng - exist_lng) < 0.0005 and abs(new_lat - exist_lat) < 0.0005:
                    return True, "名称相同+坐标接近"

            # 2. 名称高度相似 + 地址高度相似
            name_sim = self.calculate_similarity(new_name, exist_name)
            addr_sim = self.calculate_similarity(new_addr, exist_addr)

            if name_sim >= threshold and addr_sim >= threshold:
                return True, f"名称相似{name_sim:.0%}+地址相似{addr_sim:.0%}"

            # 3. 名称高度相似 + 坐标几乎相同（<20米）
            if name_sim >= threshold:
                if abs(new_lng - exist_lng) < 0.0002 and abs(new_lat - exist_lat) < 0.0002:
                    return True, f"名称相似{name_sim:.0%}+坐标几乎相同"

        return False, ""

    def search_poi(self, keyword, page=0):
        """搜索POI"""
        url = "https://map.baidu.com/"

        # 构建搜索查询
        query = f"{self.region_name}{keyword}"

        # 使用边界进行搜索
        bounds_str = ''
        if self.bounds:
            bounds_str = f'({self.bounds[0]-0.01},{self.bounds[1]-0.01};{self.bounds[2]+0.01},{self.bounds[3]+0.01})'

        params = {
            'newmap': '1',
            'reqflag': 'pcmap',
            'biz': '1',
            'from': 'webmap',
            'da_par': 'direct',
            'pcevaname': 'pc4.1',
            'qt': 's',
            'da_src': 'searchBox.button',
            'wd': query,
            'c': self.city_code,  # 使用动态城市代码
            'src': '0',
            'pn': page,
            'sug': '0',
            'l': '14',
            'b': bounds_str,
            'nn': page * 10,
            'ie': 'utf-8',
            't': str(int(time.time() * 1000)),
        }

        # 构建代理配置
        proxies = None
        if self.use_proxy and self.proxy_url:
            proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url
            }

        for retry in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=15, proxies=proxies)
                text = response.text
                return self._parse_response(text)

            except requests.exceptions.RequestException as e:
                if retry < self.max_retries - 1:
                    self.log_message.emit(f"网络错误，{self.retry_delay}秒后重试 ({retry+1}/{self.max_retries}): {str(e)}", "warning")
                    time.sleep(self.retry_delay)
                else:
                    self.log_message.emit(f"请求失败: {str(e)}", "error")
                    return []

        return []

    def _parse_response(self, text):
        """解析响应"""
        results = []
        debug_logged = False  # 只打印一次调试信息

        try:
            if text.strip().startswith('{'):
                data = json.loads(text)
            else:
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    return results

            content = data.get('content', [])
            if not content:
                content = data.get('result', {}).get('content', [])

            for item in content:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    addr = item.get('addr', '') or item.get('address', '')

                    # 获取原始坐标
                    x = item.get('x', 0) or item.get('pointx', 0)
                    y = item.get('y', 0) or item.get('pointy', 0)

                    # 调试: 打印第一个结果的原始数据
                    if not debug_logged and name:
                        self.log_message.emit(f"  [调试] 原始坐标 x={x}, y={y}, name={name[:20]}", "info")
                        debug_logged = True

                    # 转换为浮点数
                    try:
                        x = float(x) if x else 0
                        y = float(y) if y else 0
                    except:
                        x, y = 0, 0

                    if x > 0 and y > 0:
                        # 1.0版本的正确逻辑：先除以100，再墨卡托转换
                        if x > 1000:
                            x = x / 100.0
                            y = y / 100.0

                        lng, lat = self._mercator_to_bd09(x, y)

                        results.append({
                            'name': name,
                            'address': addr,
                            'lng': lng,
                            'lat': lat,
                            'uid': item.get('uid', ''),
                            'tel': item.get('tel', ''),
                            'tag': item.get('std_tag', '') or item.get('tag', ''),
                        })

        except Exception as e:
            self.log_message.emit(f"  [调试] 解析异常: {str(e)}", "warning")

        return results

    def _mercator_to_bd09(self, x, y):
        """墨卡托坐标转BD-09"""
        MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
        MC2LL = [
            [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331,
             200.9824383106796, -187.2403703815547, 91.6087516669843,
             -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
            [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289,
             96.32687599759846, -1.85204757529826, -59.36935905485877,
             47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
            [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616,
             59.74293618442277, 7.357984074871, -25.38371002664745,
             13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
            [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591,
             40.31678527705744, 0.65659298677277, -4.44255534477492,
             0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
            [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062,
             23.10934304144901, -0.00023663490511, -0.6321817810242,
             -0.00663494467042, 0.03430082397953, -0.00466043876332, 2555164.4],
            [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8,
             7.47137025468032, -0.00000353937994, -0.02145144861037,
             -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5]
        ]

        abs_y = abs(y)
        for i in range(len(MCBAND)):
            if abs_y >= MCBAND[i]:
                cD = MC2LL[i]
                break
        else:
            return x / 100000, y / 100000

        lng = cD[0] + cD[1] * abs(x)
        c = abs(y) / cD[9]
        lat = cD[2] + cD[3] * c + cD[4] * c * c + cD[5] * c * c * c + \
              cD[6] * c ** 4 + cD[7] * c ** 5 + cD[8] * c ** 6

        lng = lng * (1 if x >= 0 else -1)
        lat = lat * (1 if y >= 0 else -1)

        return lng, lat

    def run(self):
        """主运行函数"""
        self.is_running = True
        self.should_stop = False

        try:
            # 计算总任务数
            total_keywords = sum(len(kws) for kws in self.categories.values())
            current_task = 0

            category_list = list(self.categories.items())

            # 从上次进度继续
            start_cat_idx = self.progress_state['current_category_index']

            for cat_idx in range(start_cat_idx, len(category_list)):
                if self.should_stop:
                    break

                category_name, keywords = category_list[cat_idx]
                self.progress_state['current_category_index'] = cat_idx

                self.log_message.emit(f"\n{'='*40}", "info")
                self.log_message.emit(f"开始爬取: {category_name}", "info")
                self.log_message.emit(f"{'='*40}", "info")

                # 从上次关键词继续
                start_kw_idx = self.progress_state['current_keyword_index'] if cat_idx == start_cat_idx else 0

                for kw_idx in range(start_kw_idx, len(keywords)):
                    if self.should_stop:
                        break

                    keyword = keywords[kw_idx]
                    self.progress_state['current_keyword_index'] = kw_idx

                    self.log_message.emit(f"正在搜索: {keyword}", "info")

                    # 从上次页码继续
                    start_page = self.progress_state['current_page'] if (cat_idx == start_cat_idx and kw_idx == start_kw_idx) else 0
                    page = start_page
                    empty_count = 0

                    while page < 50 and empty_count < 3:
                        # 检查暂停
                        while self.is_paused and not self.should_stop:
                            time.sleep(0.5)

                        if self.should_stop:
                            break

                        self.progress_state['current_page'] = page

                        results = self.search_poi(keyword, page=page)

                        if not results:
                            empty_count += 1
                            page += 1
                            time.sleep(random.uniform(self.min_delay, self.max_delay))
                            continue

                        empty_count = 0
                        valid_count = 0
                        invalid_coord_count = 0
                        dup_count = 0
                        out_boundary_count = 0
                        debug_first = True

                        for poi in results:
                            uid = poi.get('uid', '') or f"{poi['name']}_{poi['lng']}_{poi['lat']}"
                            lng = poi.get('lng', 0)
                            lat = poi.get('lat', 0)

                            # 调试：打印第一个转换后的坐标
                            if debug_first:
                                self.log_message.emit(f"  [调试] 转换后坐标 lng={lng:.6f}, lat={lat:.6f}", "info")
                                debug_first = False

                            # 基本UID检查
                            if uid in self.progress_state['collected_uids']:
                                continue

                            # 坐标有效性检查
                            coord_valid, coord_reason = self.is_valid_coordinate(lng, lat)
                            if not coord_valid:
                                invalid_coord_count += 1
                                continue

                            # 边界检查
                            if not self.is_in_boundary(lng, lat):
                                out_boundary_count += 1
                                continue

                            # 智能去重检查
                            is_dup, dup_reason = self.is_duplicate(poi, self.progress_state['results'])
                            if is_dup:
                                dup_count += 1
                                continue

                            # 通过所有检查，添加数据
                            self.progress_state['collected_uids'].add(uid)

                            wgs_lng, wgs_lat = bd09_to_wgs84(lng, lat)

                            poi_data = {
                                '类别': category_name,
                                '名称': poi.get('name', ''),
                                '地址': poi.get('address', ''),
                                '经度_BD09': round(lng, 6),
                                '纬度_BD09': round(lat, 6),
                                '经度_WGS84': round(wgs_lng, 6),
                                '纬度_WGS84': round(wgs_lat, 6),
                                '电话': poi.get('tel', ''),
                                '详细信息': poi.get('tag', ''),
                                'uid': uid
                            }

                            self.progress_state['results'].append(poi_data)
                            self.poi_found.emit(poi_data)
                            valid_count += 1

                        # 更详细的日志
                        log_parts = [f"第{page+1}页: 获取{len(results)}条, 有效{valid_count}条"]
                        if invalid_coord_count > 0:
                            log_parts.append(f"坐标无效{invalid_coord_count}条")
                        if out_boundary_count > 0:
                            log_parts.append(f"边界外{out_boundary_count}条")
                        if dup_count > 0:
                            log_parts.append(f"重复{dup_count}条")
                        self.log_message.emit(f"  {', '.join(log_parts)}", "info")

                        # 更新进度
                        total_collected = len(self.progress_state['results'])
                        self.progress_updated.emit(
                            current_task * 50 + page,
                            total_keywords * 50,
                            f"已收集 {total_collected} 条POI"
                        )

                        page += 1
                        time.sleep(random.uniform(self.min_delay, self.max_delay))

                    current_task += 1
                    self.progress_state['current_page'] = 0

                    time.sleep(random.uniform(2, 4))

                # 统计该类别数量
                cat_count = sum(1 for r in self.progress_state['results'] if r['类别'] == category_name)
                self.progress_state['category_counts'][category_name] = cat_count
                self.category_finished.emit(category_name, cat_count)
                self.log_message.emit(f"{category_name} 完成，共 {cat_count} 条", "success")

                self.progress_state['current_keyword_index'] = 0

                time.sleep(random.uniform(3, 5))

            if not self.should_stop:
                self.crawl_finished.emit(True, f"爬取完成！共收集 {len(self.progress_state['results'])} 条POI数据")
            else:
                self.crawl_finished.emit(False, "爬取已停止")

        except Exception as e:
            self.crawl_finished.emit(False, f"爬取出错: {str(e)}")

        finally:
            self.is_running = False

    def pause(self):
        """暂停"""
        self.is_paused = True
        self.log_message.emit("爬取已暂停", "warning")

    def resume(self):
        """继续"""
        self.is_paused = False
        self.log_message.emit("爬取继续...", "info")

    def stop(self):
        """停止"""
        self.should_stop = True
        self.is_paused = False
        self.log_message.emit("正在停止...", "warning")

    def reset_progress(self):
        """重置进度"""
        self.progress_state = {
            'current_category_index': 0,
            'current_keyword_index': 0,
            'current_page': 0,
            'collected_uids': set(),
            'results': [],
            'category_counts': {}
        }

    def save_progress(self, filepath):
        """保存进度到文件"""
        state = {
            'current_category_index': self.progress_state['current_category_index'],
            'current_keyword_index': self.progress_state['current_keyword_index'],
            'current_page': self.progress_state['current_page'],
            'collected_uids': list(self.progress_state['collected_uids']),
            'results': self.progress_state['results'],
            'category_counts': self.progress_state['category_counts'],
            'categories': self.categories,
            'region_name': self.region_name
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_progress(self, filepath):
        """从文件加载进度"""
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)

        self.progress_state['current_category_index'] = state['current_category_index']
        self.progress_state['current_keyword_index'] = state['current_keyword_index']
        self.progress_state['current_page'] = state['current_page']
        self.progress_state['collected_uids'] = set(state['collected_uids'])
        self.progress_state['results'] = state['results']
        self.progress_state['category_counts'] = state['category_counts']
        self.categories = state.get('categories', self.categories)
        self.region_name = state.get('region_name', self.region_name)


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.crawler = CrawlerWorker()
        self.geojson_path = None
        self.output_dir = str(Path.home() / "Desktop")

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("百度地图POI爬虫 v2.0")
        self.setMinimumSize(1000, 700)

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ===== 顶部：文件选择区域 =====
        file_group = QGroupBox("区域设置")
        file_layout = QGridLayout(file_group)

        # 第一行：边界文件选择（支持GeoJSON和Shapefile）
        self.geojson_label = QLabel("未选择边界文件")
        self.geojson_label.setStyleSheet("color: #666;")
        file_layout.addWidget(self.geojson_label, 0, 0, 1, 2)

        self.btn_select_geojson = QPushButton("选择边界文件")
        self.btn_select_geojson.setFixedWidth(120)
        file_layout.addWidget(self.btn_select_geojson, 0, 2)

        self.btn_select_output = QPushButton("输出目录")
        self.btn_select_output.setFixedWidth(100)
        file_layout.addWidget(self.btn_select_output, 0, 3)

        # 第二行：区域名称设置
        region_label = QLabel("搜索区域名称:")
        file_layout.addWidget(region_label, 1, 0)

        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("例如: 福州市鼓楼区、北京市海淀区")
        self.region_input.setText("福州市鼓楼区")
        self.region_input.textChanged.connect(self.on_region_changed)
        file_layout.addWidget(self.region_input, 1, 1, 1, 3)

        main_layout.addWidget(file_group)

        # ===== 中部：分割器（左：类别选择，右：日志） =====
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：类别选择
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        category_group = QGroupBox("POI类别选择")
        category_layout = QVBoxLayout(category_group)

        # 全选/取消全选/新增/删除
        select_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_none = QPushButton("取消全选")
        self.btn_add_category = QPushButton("+ 新增类别")
        self.btn_add_category.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.btn_del_category = QPushButton("- 删除类别")
        self.btn_del_category.setStyleSheet("color: #f44336;")
        select_layout.addWidget(self.btn_select_all)
        select_layout.addWidget(self.btn_select_none)
        select_layout.addWidget(self.btn_add_category)
        select_layout.addWidget(self.btn_del_category)
        select_layout.addStretch()
        category_layout.addLayout(select_layout)

        # 类别复选框和编辑按钮
        self.category_checkboxes = {}
        self.category_keywords = {}  # 存储用户自定义的关键词
        self.category_edit_buttons = {}

        scroll_area = QScrollArea()
        self.category_scroll_widget = QWidget()
        self.category_scroll_layout = QGridLayout(self.category_scroll_widget)

        row = 0
        for category, keywords in DEFAULT_POI_CATEGORIES.items():
            self.add_category_to_ui(category, keywords, row)
            row += 1

        self.category_row_count = row  # 记录当前行数
        scroll_area.setWidget(self.category_scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(250)
        category_layout.addWidget(scroll_area)

        left_layout.addWidget(category_group)

        # 请求设置
        delay_group = QGroupBox("请求设置")
        delay_layout = QGridLayout(delay_group)

        # 延迟设置
        delay_layout.addWidget(QLabel("最小延迟(秒):"), 0, 0)
        self.spin_min_delay = QSpinBox()
        self.spin_min_delay.setRange(1, 10)
        self.spin_min_delay.setValue(2)
        delay_layout.addWidget(self.spin_min_delay, 0, 1)

        delay_layout.addWidget(QLabel("最大延迟(秒):"), 0, 2)
        self.spin_max_delay = QSpinBox()
        self.spin_max_delay.setRange(2, 20)
        self.spin_max_delay.setValue(4)
        delay_layout.addWidget(self.spin_max_delay, 0, 3)

        # 代理设置
        self.checkbox_proxy = QCheckBox("启用代理")
        self.checkbox_proxy.setChecked(False)
        self.checkbox_proxy.stateChanged.connect(self.on_proxy_toggled)
        delay_layout.addWidget(self.checkbox_proxy, 1, 0)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://ip:port 或 socks5://ip:port")
        self.proxy_input.setEnabled(False)
        delay_layout.addWidget(self.proxy_input, 1, 1, 1, 3)

        # 代理说明
        proxy_hint = QLabel("提示: 支持HTTP/HTTPS/SOCKS5代理")
        proxy_hint.setStyleSheet("color: #888; font-size: 11px;")
        delay_layout.addWidget(proxy_hint, 2, 0, 1, 4)

        left_layout.addWidget(delay_group)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_table = QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["类别", "数量"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_table)

        self.label_total = QLabel("总计: 0 条")
        self.label_total.setStyleSheet("font-weight: bold; font-size: 14px;")
        stats_layout.addWidget(self.label_total)

        # 数据完整度统计按钮
        self.btn_data_quality = QPushButton("📊 数据完整度统计")
        self.btn_data_quality.setStyleSheet("color: #673AB7;")
        self.btn_data_quality.clicked.connect(self.show_data_completeness)
        stats_layout.addWidget(self.btn_data_quality)

        left_layout.addWidget(stats_group)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # 右侧：日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(log_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter, 1)

        # ===== 底部：进度和控制按钮 =====
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 10, 0, 0)

        # 进度条
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v/%m")
        progress_layout.addWidget(self.progress_bar, 1)

        self.label_status = QLabel("就绪")
        self.label_status.setFixedWidth(150)
        progress_layout.addWidget(self.label_status)

        bottom_layout.addLayout(progress_layout)

        # 控制按钮
        btn_layout = QHBoxLayout()

        self.btn_start = QPushButton("▶ 开始爬取")
        self.btn_start.setFixedHeight(40)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ 暂停")
        self.btn_pause.setFixedHeight(40)
        self.btn_pause.setEnabled(False)
        btn_layout.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white;")
        btn_layout.addWidget(self.btn_stop)

        btn_layout.addSpacing(20)

        self.btn_save_progress = QPushButton("💾 保存进度")
        self.btn_save_progress.setFixedHeight(40)
        btn_layout.addWidget(self.btn_save_progress)

        self.btn_load_progress = QPushButton("📂 加载进度")
        self.btn_load_progress.setFixedHeight(40)
        btn_layout.addWidget(self.btn_load_progress)

        btn_layout.addSpacing(20)

        self.btn_export = QPushButton("📤 导出数据")
        self.btn_export.setFixedHeight(40)
        self.btn_export.setStyleSheet("background-color: #2196F3; color: white;")
        btn_layout.addWidget(self.btn_export)

        bottom_layout.addLayout(btn_layout)

        main_layout.addWidget(bottom_widget)

    def connect_signals(self):
        """连接信号"""
        # 按钮信号
        self.btn_select_geojson.clicked.connect(self.select_geojson)
        self.btn_select_output.clicked.connect(self.select_output_dir)
        self.btn_select_all.clicked.connect(self.select_all_categories)
        self.btn_select_none.clicked.connect(self.select_no_categories)
        self.btn_add_category.clicked.connect(self.add_new_category)
        self.btn_del_category.clicked.connect(self.delete_category)

        self.btn_start.clicked.connect(self.start_crawl)
        self.btn_pause.clicked.connect(self.pause_crawl)
        self.btn_stop.clicked.connect(self.stop_crawl)

        self.btn_save_progress.clicked.connect(self.save_progress)
        self.btn_load_progress.clicked.connect(self.load_progress)
        self.btn_export.clicked.connect(self.export_data)

        # 爬虫信号
        self.crawler.progress_updated.connect(self.update_progress)
        self.crawler.log_message.connect(self.add_log)
        self.crawler.poi_found.connect(self.on_poi_found)
        self.crawler.category_finished.connect(self.on_category_finished)
        self.crawler.crawl_finished.connect(self.on_crawl_finished)

    def select_geojson(self):
        """选择边界文件（支持GeoJSON和Shapefile）"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择边界文件", "",
            "边界文件 (*.geojson *.json *.shp);;GeoJSON (*.geojson *.json);;Shapefile (*.shp)"
        )

        if filepath:
            self.geojson_path = filepath
            success, msg = self.crawler.load_boundary_file(filepath)

            if success:
                self.geojson_label.setText(f"✓ {os.path.basename(filepath)}")
                self.geojson_label.setStyleSheet("color: #4CAF50;")
                self.add_log(msg, "success")
                # 根据当前输入的区域名称设置城市代码
                current_region = self.region_input.text().strip()
                if current_region:
                    self.crawler.city_code = get_city_code(current_region)
                self.add_log(f"当前城市代码: {self.crawler.city_code} (可修改“搜索区域名称”来更新)", "info")
            else:
                self.geojson_label.setText("加载失败")
                self.geojson_label.setStyleSheet("color: #f44336;")
                self.add_log(msg, "error")

    def on_region_changed(self, text):
        """区域名称变化"""
        if text.strip():
            self.crawler.region_name = text.strip()
            # 自动更新城市代码
            old_code = self.crawler.city_code
            self.crawler.city_code = get_city_code(text.strip())
            if self.crawler.city_code != old_code:
                self.add_log(f"城市代码已更新: {self.crawler.city_code}", "info")

    def select_output_dir(self):
        """选择输出目录"""
        dirpath = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir)
        if dirpath:
            self.output_dir = dirpath
            self.add_log(f"输出目录: {dirpath}", "info")

    def select_all_categories(self):
        """全选类别"""
        for cb in self.category_checkboxes.values():
            cb.setChecked(True)

    def select_no_categories(self):
        """取消全选"""
        for cb in self.category_checkboxes.values():
            cb.setChecked(False)

    def on_proxy_toggled(self, state):
        """代理开关切换"""
        enabled = state == Qt.Checked
        self.proxy_input.setEnabled(enabled)
        if not enabled:
            self.proxy_input.clear()

    def add_category_to_ui(self, category, keywords, row):
        """添加类别到UI"""
        # 复选框
        cb = QCheckBox(category)
        cb.setChecked(True)
        self.category_checkboxes[category] = cb
        self.category_keywords[category] = keywords.copy()
        self.category_scroll_layout.addWidget(cb, row, 0)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setFixedWidth(50)
        edit_btn.setStyleSheet("font-size: 11px; padding: 2px;")
        edit_btn.clicked.connect(lambda checked, cat=category: self.edit_keywords(cat))
        self.category_edit_buttons[category] = edit_btn
        self.category_scroll_layout.addWidget(edit_btn, row, 1)

    def add_new_category(self):
        """新增POI类别"""
        dialog = AddCategoryDialog(self)

        if dialog.exec_() == QDialog.Accepted:
            name = dialog.get_category_name()
            keywords = dialog.get_keywords()

            # 检查是否重名
            if name in self.category_checkboxes:
                QMessageBox.warning(self, "警告", f"类别 [{name}] 已存在！")
                return

            # 添加到UI
            self.add_category_to_ui(name, keywords, self.category_row_count)
            self.category_row_count += 1

            self.add_log(f"已添加新类别: [{name}] ({len(keywords)}个关键词)", "success")

    def delete_category(self):
        """删除选中的类别"""
        # 获取选中的类别
        selected = [name for name, cb in self.category_checkboxes.items() if cb.isChecked()]

        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要删除的类别")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除以下 {len(selected)} 个类别吗？\n\n" + "\n".join(selected),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for name in selected:
                # 从UI移除
                if name in self.category_checkboxes:
                    cb = self.category_checkboxes[name]
                    cb.setParent(None)
                    del self.category_checkboxes[name]

                if name in self.category_edit_buttons:
                    btn = self.category_edit_buttons[name]
                    btn.setParent(None)
                    del self.category_edit_buttons[name]

                if name in self.category_keywords:
                    del self.category_keywords[name]

            self.add_log(f"已删除 {len(selected)} 个类别", "warning")

    def edit_keywords(self, category):
        """编辑类别关键词"""
        current_keywords = self.category_keywords.get(category, [])
        dialog = KeywordsEditDialog(category, current_keywords, self)

        if dialog.exec_() == QDialog.Accepted:
            new_keywords = dialog.get_keywords()
            if new_keywords:
                self.category_keywords[category] = new_keywords
                self.add_log(f"已更新 [{category}] 的关键词 ({len(new_keywords)}个)", "success")
            else:
                QMessageBox.warning(self, "警告", "关键词列表不能为空！")

    def start_crawl(self):
        """开始爬取"""
        if not self.geojson_path:
            QMessageBox.warning(self, "警告", "请先选择边界文件（GeoJSON或Shapefile）！")
            return

        # 获取选中的类别（使用用户自定义的关键词）
        selected_categories = {}
        for name, cb in self.category_checkboxes.items():
            if cb.isChecked():
                # 优先使用自定义关键词，如果没有则使用默认（用户新增的类别已保存在category_keywords中）
                selected_categories[name] = self.category_keywords.get(name, DEFAULT_POI_CATEGORIES.get(name, []))

        if not selected_categories:
            QMessageBox.warning(self, "警告", "请至少选择一个POI类别！")
            return

        # 设置爬虫参数
        self.crawler.categories = selected_categories
        self.crawler.min_delay = self.spin_min_delay.value()
        self.crawler.max_delay = self.spin_max_delay.value()

        # 设置代理
        self.crawler.use_proxy = self.checkbox_proxy.isChecked()
        if self.crawler.use_proxy:
            proxy_text = self.proxy_input.text().strip()
            if proxy_text:
                self.crawler.proxy_url = proxy_text
                self.add_log(f"已启用代理: {proxy_text}", "info")
            else:
                QMessageBox.warning(self, "警告", "请输入代理地址！")
                return
        else:
            self.crawler.proxy_url = None

        # 如果没有已有进度，重置
        if not self.crawler.progress_state['results']:
            self.crawler.reset_progress()
            self.stats_table.setRowCount(0)

        # 更新UI状态
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_select_geojson.setEnabled(False)

        self.label_status.setText("爬取中...")
        self.add_log("开始爬取...", "info")

        # 启动爬虫线程
        self.crawler.start()

    def pause_crawl(self):
        """暂停/继续"""
        if self.crawler.is_paused:
            self.crawler.resume()
            self.btn_pause.setText("⏸ 暂停")
            self.label_status.setText("爬取中...")
        else:
            self.crawler.pause()
            self.btn_pause.setText("▶ 继续")
            self.label_status.setText("已暂停")

    def stop_crawl(self):
        """停止爬取"""
        reply = QMessageBox.question(
            self, "确认", "确定要停止爬取吗？\n进度可以保存后继续。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.crawler.stop()

    def save_progress(self):
        """保存进度"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存进度", f"{self.output_dir}/crawl_progress.json", "JSON Files (*.json)"
        )

        if filepath:
            try:
                self.crawler.save_progress(filepath)
                self.add_log(f"进度已保存: {filepath}", "success")
                QMessageBox.information(self, "成功", "进度保存成功！")
            except Exception as e:
                self.add_log(f"保存失败: {str(e)}", "error")

    def load_progress(self):
        """加载进度"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "加载进度", "", "JSON Files (*.json)"
        )

        if filepath:
            try:
                self.crawler.load_progress(filepath)

                # 更新统计表
                self.stats_table.setRowCount(0)
                for cat, count in self.crawler.progress_state['category_counts'].items():
                    self.add_stats_row(cat, count)

                total = len(self.crawler.progress_state['results'])
                self.label_total.setText(f"总计: {total} 条")

                self.add_log(f"进度已加载: {filepath}", "success")
                self.add_log(f"已有 {total} 条数据，可继续爬取", "info")

                QMessageBox.information(self, "成功", f"进度加载成功！\n已有 {total} 条数据。")
            except Exception as e:
                self.add_log(f"加载失败: {str(e)}", "error")

    def export_data(self):
        """导出数据"""
        if not self.crawler.progress_state['results']:
            QMessageBox.warning(self, "警告", "没有数据可导出！")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出数据", f"{self.output_dir}/poi_data.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv);;JSON Files (*.json)"
        )

        if filepath:
            try:
                df = pd.DataFrame(self.crawler.progress_state['results'])

                if filepath.endswith('.xlsx'):
                    df.to_excel(filepath, index=False, engine='openpyxl')
                elif filepath.endswith('.csv'):
                    df.to_csv(filepath, index=False, encoding='utf-8-sig')
                elif filepath.endswith('.json'):
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(self.crawler.progress_state['results'], f, ensure_ascii=False, indent=2)

                self.add_log(f"数据已导出: {filepath}", "success")
                QMessageBox.information(self, "成功", f"数据导出成功！\n共 {len(df)} 条记录。")
            except Exception as e:
                self.add_log(f"导出失败: {str(e)}", "error")

    def show_data_completeness(self):
        """显示数据完整度统计"""
        results = self.crawler.progress_state['results']

        if not results:
            QMessageBox.information(self, "提示", "暂无数据，请先爬取POI数据")
            return

        total = len(results)

        # 定义要统计的字段
        fields = {
            '名称': '名称',
            '地址': '地址',
            '电话': '电话',
            '详细信息': '详细信息',
            '经度_BD09': '经度',
            '纬度_BD09': '纬度'
        }

        # 统计每个字段的填充率
        stats_html = f"<h3>📊 数据完整度统计</h3>"
        stats_html += f"<p><b>总记录数:</b> {total} 条</p>"
        stats_html += "<hr>"
        stats_html += "<table style='width:100%; border-collapse:collapse;'>"
        stats_html += "<tr style='background:#f0f0f0;'><th style='padding:8px; text-align:left;'>字段</th><th style='padding:8px;'>有值</th><th style='padding:8px;'>缺失</th><th style='padding:8px;'>填充率</th></tr>"

        for field_key, field_name in fields.items():
            filled = sum(1 for r in results if r.get(field_key) and str(r.get(field_key)).strip())
            missing = total - filled
            rate = filled / total * 100 if total > 0 else 0

            # 根据填充率设置颜色
            if rate >= 90:
                color = "#4CAF50"  # 绿色
            elif rate >= 70:
                color = "#FF9800"  # 橙色
            else:
                color = "#f44336"  # 红色

            stats_html += f"<tr>"
            stats_html += f"<td style='padding:6px; border-bottom:1px solid #ddd;'>{field_name}</td>"
            stats_html += f"<td style='padding:6px; border-bottom:1px solid #ddd; text-align:center;'>{filled}</td>"
            stats_html += f"<td style='padding:6px; border-bottom:1px solid #ddd; text-align:center;'>{missing}</td>"
            stats_html += f"<td style='padding:6px; border-bottom:1px solid #ddd; text-align:center;'><b style='color:{color};'>{rate:.1f}%</b></td>"
            stats_html += "</tr>"

        stats_html += "</table>"

        # 各类别统计
        stats_html += "<hr><h4>各类别数量:</h4>"
        category_counts = {}
        for r in results:
            cat = r.get('类别', '未知')
            category_counts[cat] = category_counts.get(cat, 0) + 1

        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            stats_html += f"<p>• {cat}: <b>{count}</b> 条 ({pct:.1f}%)</p>"

        # 显示对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("数据完整度统计")
        dialog.setMinimumSize(450, 500)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(stats_html)
        layout.addWidget(text_edit)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)

        dialog.exec_()

    def update_progress(self, current, total, message):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.label_status.setText(message)

    def add_log(self, message, level="info"):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        colors = {
            "info": "#333",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#f44336"
        }
        color = colors.get(level, "#333")

        html = f'<span style="color: #999;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        self.log_text.append(html)

        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_poi_found(self, poi):
        """找到POI时"""
        total = len(self.crawler.progress_state['results'])
        self.label_total.setText(f"总计: {total} 条")

    def on_category_finished(self, category, count):
        """类别完成时"""
        self.add_stats_row(category, count)

    def add_stats_row(self, category, count):
        """添加统计行"""
        row = self.stats_table.rowCount()
        self.stats_table.insertRow(row)
        self.stats_table.setItem(row, 0, QTableWidgetItem(category))
        self.stats_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def on_crawl_finished(self, success, message):
        """爬取完成时"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_select_geojson.setEnabled(True)
        self.btn_pause.setText("⏸ 暂停")

        if success:
            self.label_status.setText("完成")
            self.add_log(message, "success")

            # 自动保存
            auto_save_path = f"{self.output_dir}/poi_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            try:
                df = pd.DataFrame(self.crawler.progress_state['results'])
                df.to_excel(auto_save_path, index=False, engine='openpyxl')
                self.add_log(f"数据已自动保存: {auto_save_path}", "success")
            except:
                pass

            QMessageBox.information(self, "完成", message)
        else:
            self.label_status.setText("已停止")
            self.add_log(message, "warning")

    def closeEvent(self, event):
        """关闭窗口时"""
        if self.crawler.is_running:
            reply = QMessageBox.question(
                self, "确认", "爬虫正在运行，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.crawler.stop()
                self.crawler.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ==================== 程序入口 ====================
def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
