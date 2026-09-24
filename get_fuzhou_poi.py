#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
福州市主城区八大类服务设施POI数据采集脚本
使用百度地图Place API获取POI数据
"""

import requests
import json
import time
import csv
from datetime import datetime

# 百度地图API配置
import os
BAIDU_AK = os.environ.get("BAIDU_MAP_AK", "")
PLACE_API_URL = "https://api.map.baidu.com/place/v2/search"

# 福州市主城区中心点坐标（经纬度）
FUZHOU_CENTER = {
    "lat": 26.0745,
    "lng": 119.2965
}

# 搜索半径（米）- 可根据需要调整
SEARCH_RADIUS = 10000

# 八大类POI类型映射（根据百度地图POI分类）
POI_CATEGORIES = {
    "餐饮设施": ["美食", "中餐厅", "外国餐厅", "小吃快餐店", "蛋糕甜品店", "咖啡厅", "茶艺馆", "酒吧"],
    "超市商场": ["购物", "商场", "超市", "便利店", "购物中心"],
    "医疗设施": ["医疗", "综合医院", "专科医院", "诊所", "药店", "体检机构"],
    "教育设施": ["教育培训", "幼儿园", "小学", "中学", "高等院校", "成人教育", "亲子教育", "培训机构"],
    "公园广场": ["旅游景点", "公园", "广场", "植物园", "动物园"],
    "交通设施": ["交通设施", "地铁站", "公交车站", "长途汽车站", "火车站", "飞机场", "港口"],
    "金融设施": ["金融", "银行", "ATM", "信用社"],
    "休闲娱乐设施": ["休闲娱乐", "电影院", "KTV", "游戏场所", "体育场馆", "健身中心", "运动场所"]
}


class BaiduPOICollector:
    """百度地图POI数据采集器"""

    def __init__(self, ak, center_lat, center_lng, radius):
        self.ak = ak
        self.center_lat = center_lat
        self.center_lng = center_lng
        self.radius = radius
        self.total_results = []

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
            "page_size": 20,  # 每页最多20条
            "page_num": page_num,
            "scope": 2  # 返回详细信息
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
        :param category_name: 类别名称
        :param keywords: 关键词列表
        :return: POI列表
        """
        print(f"\n{'='*50}")
        print(f"开始采集: {category_name}")
        print(f"{'='*50}")

        category_pois = []
        poi_ids = set()  # 用于去重

        for keyword in keywords:
            print(f"\n正在搜索: {keyword}")
            page = 0

            while page < 20:  # 百度地图API最多支持20页
                result = self.search_poi(query=keyword, page_num=page)

                if not result or "results" not in result:
                    break

                results = result.get("results", [])
                if not results:
                    break

                # 处理结果
                for poi in results:
                    poi_id = poi.get("uid")
                    if poi_id and poi_id not in poi_ids:
                        poi_ids.add(poi_id)
                        poi_data = {
                            "类别": category_name,
                            "名称": poi.get("name", ""),
                            "地址": poi.get("address", ""),
                            "经度": poi.get("location", {}).get("lng", ""),
                            "纬度": poi.get("location", {}).get("lat", ""),
                            "电话": poi.get("telephone", ""),
                            "详细信息": poi.get("detail_info", {}).get("tag", ""),
                            "uid": poi_id
                        }
                        category_pois.append(poi_data)

                print(f"  第{page+1}页: 获取{len(results)}条数据")

                # 判断是否还有更多数据
                total = result.get("total", 0)
                if (page + 1) * 20 >= total:
                    break

                page += 1
                time.sleep(0.2)  # 避免请求过快

            time.sleep(0.5)  # 每个关键词之间稍作延迟

        print(f"\n{category_name} 共采集到 {len(category_pois)} 条数据（已去重）")
        return category_pois

    def collect_all_categories(self):
        """采集所有类别的POI数据"""
        print(f"\n开始采集福州市主城区POI数据")
        print(f"中心点坐标: ({self.center_lat}, {self.center_lng})")
        print(f"搜索半径: {self.radius}米")
        print(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        all_results = []
        summary = {}

        for category_name, keywords in POI_CATEGORIES.items():
            pois = self.collect_category_poi(category_name, keywords)
            all_results.extend(pois)
            summary[category_name] = len(pois)

        self.total_results = all_results

        # 打印汇总信息
        print(f"\n{'='*50}")
        print("采集完成！数据汇总：")
        print(f"{'='*50}")
        for category, count in summary.items():
            print(f"{category}: {count}条")
        print(f"总计: {len(all_results)}条")

        return all_results

    def save_to_csv(self, filename="fuzhou_poi_data.csv"):
        """保存数据到CSV文件"""
        if not self.total_results:
            print("没有数据可保存")
            return

        filepath = f"c:\\Users\\邱煜\\Desktop\\地理ai\\生活区\\{filename}"

        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                fieldnames = ["类别", "名称", "地址", "经度", "纬度", "电话", "详细信息", "uid"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.total_results)

            print(f"\n数据已保存到: {filepath}")
        except Exception as e:
            print(f"保存CSV文件时出错: {e}")

    def save_to_json(self, filename="fuzhou_poi_data.json"):
        """保存数据到JSON文件"""
        if not self.total_results:
            print("没有数据可保存")
            return

        filepath = f"c:\\Users\\邱煜\\Desktop\\地理ai\\生活区\\{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.total_results, f, ensure_ascii=False, indent=2)

            print(f"数据已保存到: {filepath}")
        except Exception as e:
            print(f"保存JSON文件时出错: {e}")


def main():
    """主函数"""
    # 创建采集器实例
    collector = BaiduPOICollector(
        ak=BAIDU_AK,
        center_lat=FUZHOU_CENTER["lat"],
        center_lng=FUZHOU_CENTER["lng"],
        radius=SEARCH_RADIUS
    )

    # 采集所有类别数据
    collector.collect_all_categories()

    # 保存数据
    collector.save_to_csv()
    collector.save_to_json()

    print("\n所有任务完成！")


if __name__ == "__main__":
    main()
