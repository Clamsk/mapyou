#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
福州市鼓楼区服务设施POI数据采集脚本（测试版）
使用百度地图Place API获取POI数据
基于鼓楼区.geojson边界进行搜索
"""

import requests
import json
import time
import csv
import math
from datetime import datetime
from shapely.geometry import shape, Point, MultiPolygon
from shapely.ops import unary_union
import pandas as pd


# ==================== 坐标转换模块 ====================
# BD-09 -> GCJ-02 -> WGS-84

# 坐标转换常量
X_PI = 3.14159265358979324 * 3000.0 / 180.0
PI = 3.1415926535897932384626
A = 6378245.0  # 长半轴
EE = 0.00669342162296594323  # 扁率


def bd09_to_gcj02(bd_lng, bd_lat):
    """BD-09 转 GCJ-02（百度坐标转火星坐标）"""
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj_lng, gcj_lat


def gcj02_to_wgs84(gcj_lng, gcj_lat):
    """GCJ-02 转 WGS-84（火星坐标转GPS坐标）"""
    if out_of_china(gcj_lng, gcj_lat):
        return gcj_lng, gcj_lat

    dlat = transform_lat(gcj_lng - 105.0, gcj_lat - 35.0)
    dlng = transform_lng(gcj_lng - 105.0, gcj_lat - 35.0)
    radlat = gcj_lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    wgs_lat = gcj_lat - dlat
    wgs_lng = gcj_lng - dlng
    return wgs_lng, wgs_lat


def bd09_to_wgs84(bd_lng, bd_lat):
    """BD-09 直接转 WGS-84（百度坐标转GPS坐标）"""
    gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
    wgs_lng, wgs_lat = gcj02_to_wgs84(gcj_lng, gcj_lat)
    return wgs_lng, wgs_lat


def transform_lat(lng, lat):
    """纬度转换辅助函数"""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 *
            math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 *
            math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def transform_lng(lng, lat):
    """经度转换辅助函数"""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 *
            math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 *
            math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def out_of_china(lng, lat):
    """判断是否在中国境外"""
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)

# 百度地图API配置
import os
BAIDU_AK = os.environ.get("BAIDU_MAP_AK", "")
PLACE_API_URL = "https://api.map.baidu.com/place/v2/search"

# GeoJSON文件路径
GEOJSON_PATH = os.environ.get("MAPYOU_BOUNDARY", "鼓楼区.geojson")

# 测试用：只采集餐饮设施
TEST_CATEGORY = {
    "餐饮设施": ["美食", "中餐厅", "快餐店", "小吃", "甜品店", "咖啡厅"]
}

# 八大类POI类型映射（完整版本，供后续使用）
POI_CATEGORIES = {
    "餐饮设施": ["美食", "中餐厅", "快餐店", "小吃", "甜品店", "咖啡厅", "茶艺馆"],
    "超市商场": ["购物", "商场", "超市", "便利店", "购物中心"],
    "医疗设施": ["医疗", "综合医院", "专科医院", "诊所", "药店"],
    "教育设施": ["幼儿园", "小学", "中学", "高等院校", "培训机构"],
    "公园广场": ["公园", "广场", "植物园"],
    "交通设施": ["地铁站", "公交车站", "停车场"],
    "金融设施": ["银行", "ATM"],
    "休闲娱乐设施": ["电影院", "KTV", "健身中心", "体育场馆"]
}


class GulouPOICollector:
    """鼓楼区POI数据采集器"""

    def __init__(self, ak, geojson_path):
        self.ak = ak
        self.geojson_path = geojson_path
        self.total_results = []
        self.boundary = None
        self.center_lat = None
        self.center_lng = None
        self.radius = None

        # 加载边界
        self._load_boundary()

    def _load_boundary(self):
        """加载GeoJSON边界文件"""
        print("正在加载鼓楼区边界...")

        with open(self.geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        # 合并所有街道的多边形为一个整体边界
        polygons = []
        for feature in geojson_data.get('features', []):
            geom = shape(feature['geometry'])
            if isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    polygons.append(poly)
            else:
                polygons.append(geom)

        # 合并所有多边形
        self.boundary = unary_union(polygons)

        # 计算边界的中心点和外接圆半径
        centroid = self.boundary.centroid
        self.center_lat = centroid.y
        self.center_lng = centroid.x

        # 计算边界的外接矩形，用于确定搜索半径
        minx, miny, maxx, maxy = self.boundary.bounds

        # 简单估算搜索半径（单位：米）
        # 经度1度约111km，纬度1度约111km*cos(lat)
        import math
        lat_diff = (maxy - miny) * 111000
        lng_diff = (maxx - minx) * 111000 * math.cos(math.radians(self.center_lat))
        self.radius = int(max(lat_diff, lng_diff) / 2 * 1.2)  # 增加20%余量

        print(f"边界加载完成！")
        print(f"中心点: ({self.center_lat:.6f}, {self.center_lng:.6f})")
        print(f"搜索半径: {self.radius}米")
        print(f"边界范围: 经度[{minx:.6f}, {maxx:.6f}], 纬度[{miny:.6f}, {maxy:.6f}]")

    def is_in_boundary(self, lng, lat):
        """判断点是否在鼓楼区边界内"""
        point = Point(lng, lat)
        return self.boundary.contains(point)

    def search_poi(self, query, tag="", page_num=0):
        """
        搜索POI数据
        :param query: 搜索关键词
        :param tag: POI分类标签
        :param page_num: 页码（0-19）
        :return: 搜索结果
        """
        params = {
            "query": query,
            "tag": tag,
            "location": f"{self.center_lat},{self.center_lng}",
            "radius": self.radius,
            "output": "json",
            "ak": self.ak,
            "page_size": 20,
            "page_num": page_num,
            "scope": 2,
            "coord_type": 1  # WGS84坐标
        }

        try:
            response = requests.get(PLACE_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == 0:
                return data
            else:
                print(f"API错误: {data.get('message', '未知错误')} (状态码: {data.get('status')})")
                return None

        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return None

    def collect_category_poi(self, category_name, keywords):
        """
        采集某一类别的所有POI数据
        """
        print(f"\n{'='*50}")
        print(f"开始采集: {category_name}")
        print(f"{'='*50}")

        category_pois = []
        poi_ids = set()

        for keyword in keywords:
            print(f"\n正在搜索: {keyword}")
            page = 0
            keyword_count = 0

            while page < 20:
                result = self.search_poi(query=keyword, page_num=page)

                if not result or "results" not in result:
                    break

                results = result.get("results", [])
                if not results:
                    break

                for poi in results:
                    poi_id = poi.get("uid")
                    lng = poi.get("location", {}).get("lng", 0)
                    lat = poi.get("location", {}).get("lat", 0)

                    # 检查是否在边界内且未重复
                    if poi_id and poi_id not in poi_ids:
                        if self.is_in_boundary(lng, lat):
                            poi_ids.add(poi_id)
                            # 转换坐标：BD-09 -> WGS-84
                            wgs_lng, wgs_lat = bd09_to_wgs84(lng, lat)
                            poi_data = {
                                "类别": category_name,
                                "名称": poi.get("name", ""),
                                "地址": poi.get("address", ""),
                                "经度_BD09": lng,
                                "纬度_BD09": lat,
                                "经度_WGS84": round(wgs_lng, 6),
                                "纬度_WGS84": round(wgs_lat, 6),
                                "电话": poi.get("telephone", ""),
                                "详细信息": poi.get("detail_info", {}).get("tag", "") if poi.get("detail_info") else "",
                                "uid": poi_id
                            }
                            category_pois.append(poi_data)
                            keyword_count += 1

                print(f"  第{page+1}页: 获取{len(results)}条, 边界内有效{keyword_count}条")

                total = result.get("total", 0)
                if (page + 1) * 20 >= total:
                    break

                page += 1
                time.sleep(0.3)

            time.sleep(0.5)

        print(f"\n{category_name} 共采集到 {len(category_pois)} 条数据（已去重、已过滤边界）")
        return category_pois

    def collect_test_category(self):
        """测试采集：只采集餐饮设施"""
        print(f"\n开始采集鼓楼区POI数据（测试模式）")
        print(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        all_results = []

        for category_name, keywords in TEST_CATEGORY.items():
            pois = self.collect_category_poi(category_name, keywords)
            all_results.extend(pois)

        self.total_results = all_results

        print(f"\n{'='*50}")
        print(f"测试采集完成！共获取 {len(all_results)} 条数据")
        print(f"{'='*50}")

        return all_results

    def collect_all_categories(self):
        """采集所有八大类设施"""
        print(f"\n开始采集鼓楼区八大类POI数据")
        print(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        all_results = []
        summary = {}

        for category_name, keywords in POI_CATEGORIES.items():
            pois = self.collect_category_poi(category_name, keywords)
            all_results.extend(pois)
            summary[category_name] = len(pois)

        self.total_results = all_results

        print(f"\n{'='*50}")
        print("采集完成！数据汇总：")
        print(f"{'='*50}")
        for category, count in summary.items():
            print(f"{category}: {count}条")
        print(f"总计: {len(all_results)}条")

        return all_results

    def save_to_excel(self, filename="gulou_poi_test.xlsx"):
        """保存数据到Excel文件"""
        if not self.total_results:
            print("没有数据可保存")
            return

        filepath = f"c:\\Users\\邱煜\\Desktop\\地理ai\\生活区\\{filename}"

        try:
            df = pd.DataFrame(self.total_results)
            df.to_excel(filepath, index=False, engine='openpyxl')
            print(f"\n数据已保存到Excel: {filepath}")
        except Exception as e:
            print(f"保存Excel文件时出错: {e}")

    def save_to_csv(self, filename="gulou_poi_test.csv"):
        """保存数据到CSV文件"""
        if not self.total_results:
            print("没有数据可保存")
            return

        filepath = f"c:\\Users\\邱煜\\Desktop\\地理ai\\生活区\\{filename}"

        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                fieldnames = ["类别", "名称", "地址", "经度_BD09", "纬度_BD09",
                             "经度_WGS84", "纬度_WGS84", "电话", "详细信息", "uid"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.total_results)

            print(f"数据已保存到CSV: {filepath}")
        except Exception as e:
            print(f"保存CSV文件时出错: {e}")

    def save_to_json(self, filename="gulou_poi_test.json"):
        """保存数据到JSON文件"""
        if not self.total_results:
            print("没有数据可保存")
            return

        filepath = f"c:\\Users\\邱煜\\Desktop\\地理ai\\生活区\\{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.total_results, f, ensure_ascii=False, indent=2)

            print(f"数据已保存到JSON: {filepath}")
        except Exception as e:
            print(f"保存JSON文件时出错: {e}")


def main():
    """主函数"""
    # 创建采集器实例
    collector = GulouPOICollector(
        ak=BAIDU_AK,
        geojson_path=GEOJSON_PATH
    )

    # 采集八大类设施
    collector.collect_all_categories()

    # 保存数据
    collector.save_to_excel("gulou_poi_all.xlsx")
    collector.save_to_csv("gulou_poi_all.csv")
    collector.save_to_json("gulou_poi_all.json")

    print("\n所有任务完成！")


if __name__ == "__main__":
    main()
