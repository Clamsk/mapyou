#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
百度地图POI数据爬虫
直接从百度地图网页端爬取POI数据，绕过API配额限制
"""

import requests
import json
import time
import random
import math
import re
from datetime import datetime
from shapely.geometry import shape, Point, MultiPolygon
from shapely.ops import unary_union
import pandas as pd
from urllib.parse import quote

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


# ==================== POI爬虫类 ====================

class BaiduPOICrawler:
    """百度地图POI爬虫"""

    def __init__(self, geojson_path):
        self.session = requests.Session()
        self.geojson_path = geojson_path
        self.boundary = None
        self.bounds = None
        self.total_results = []

        # 设置请求头，模拟浏览器
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://map.baidu.com/',
        }
        self.session.headers.update(self.headers)

        # 加载边界
        self._load_boundary()

    def _load_boundary(self):
        """加载GeoJSON边界"""
        print("正在加载区域边界...")
        with open(self.geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

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

        print(f"边界加载完成！")
        print(f"范围: 经度[{self.bounds[0]:.6f}, {self.bounds[2]:.6f}], 纬度[{self.bounds[1]:.6f}, {self.bounds[3]:.6f}]")

    def is_in_boundary(self, lng, lat):
        """判断点是否在边界内"""
        point = Point(lng, lat)
        return self.boundary.contains(point)

    def _random_delay(self, min_sec=1, max_sec=3):
        """随机延迟，避免被封"""
        time.sleep(random.uniform(min_sec, max_sec))

    def search_poi_web(self, keyword, region="福州市鼓楼区", page=0):
        """
        通过百度地图网页接口搜索POI
        """
        # 百度地图搜索API（网页版）
        url = "https://map.baidu.com/"

        # 构建请求参数
        params = {
            'newmap': '1',
            'reqflag': 'pcmap',
            'biz': '1',
            'from': 'webmap',
            'da_par': 'direct',
            'pcevaname': 'pc4.1',
            'qt': 's',
            'da_src': 'searchBox.button',
            'wd': f'{region}{keyword}',
            'c': '131',  # 福州市城市代码
            'src': '0',
            'wd2': '',
            'pn': page,
            'sug': '0',
            'l': '13',
            'b': f'({self.bounds[0]},{self.bounds[1]};{self.bounds[2]},{self.bounds[3]})',
            'from': 'webmap',
            'biz_forward': '{"scaler":1,"styles":"pl"}',
            'sug_forward': '',
            'auth': '',
            'device_ratio': '1',
            'tn': 'B_NORMAL_MAP',
            'nn': page * 10,
            'ie': 'utf-8',
        }

        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()

            # 解析返回的数据
            text = response.text

            # 尝试提取JSON数据
            results = self._parse_response(text)
            return results

        except Exception as e:
            print(f"请求错误: {e}")
            return None

    def search_poi_suggestion(self, keyword, region="福州"):
        """
        使用百度地图Suggestion接口搜索
        """
        url = "https://map.baidu.com/su"

        params = {
            'wd': f'{keyword}',
            'cid': '131',  # 福州市
            'type': '0',
            's': '1',
            't': str(int(time.time() * 1000)),
            'callback': 'callback',
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            text = response.text

            # 解析JSONP响应
            if 'callback(' in text:
                json_str = text[text.find('(')+1:text.rfind(')')]
                data = json.loads(json_str)
                return data.get('s', [])

        except Exception as e:
            print(f"Suggestion请求错误: {e}")

        return []

    def search_poi_place(self, keyword, region="鼓楼区", page=0):
        """
        使用百度地图Place搜索接口（更稳定）
        """
        # 计算边界中心点
        center_lng = (self.bounds[0] + self.bounds[2]) / 2
        center_lat = (self.bounds[1] + self.bounds[3]) / 2

        url = "https://map.baidu.com/"

        # 使用更详细的查询
        query = f"福州市{region}{keyword}"

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
            'c': '131',
            'src': '0',
            'pn': page,
            'sug': '0',
            'l': '14',
            'b': f'({self.bounds[0]-0.01},{self.bounds[1]-0.01};{self.bounds[2]+0.01},{self.bounds[3]+0.01})',
            'nn': page * 10,
            'ie': 'utf-8',
            't': str(int(time.time() * 1000)),
        }

        try:
            response = self.session.get(url, params=params, timeout=15)
            text = response.text

            # 解析响应
            results = self._parse_baidu_response(text)
            return results

        except Exception as e:
            print(f"Place搜索错误: {e}")
            return []

    def _parse_baidu_response(self, text):
        """解析百度地图响应"""
        results = []

        try:
            # 尝试直接解析JSON
            if text.strip().startswith('{'):
                data = json.loads(text)
            else:
                # 尝试提取JSON部分
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    return results

            # 解析content字段
            content = data.get('content', [])
            if not content:
                content = data.get('result', {}).get('content', [])

            for item in content:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    addr = item.get('addr', '') or item.get('address', '')

                    # 获取坐标
                    x = item.get('x', 0)
                    y = item.get('y', 0)

                    # 百度地图返回的坐标需要除以100
                    if x > 1000:
                        x = x / 100.0
                        y = y / 100.0

                    if x > 0 and y > 0:
                        # 墨卡托转经纬度
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

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"解析错误: {e}")

        return results

    def _parse_response(self, text):
        """解析响应数据"""
        return self._parse_baidu_response(text)

    def _mercator_to_bd09(self, x, y):
        """墨卡托坐标转BD-09"""
        # 百度墨卡托投影逆转换
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

    def crawl_category(self, category_name, keywords):
        """爬取一个类别的POI"""
        print(f"\n{'='*50}")
        print(f"开始爬取: {category_name}")
        print(f"{'='*50}")

        category_pois = []
        poi_uids = set()

        for keyword in keywords:
            print(f"\n正在搜索: {keyword}")
            page = 0
            empty_count = 0

            while page < 50 and empty_count < 3:
                results = self.search_poi_place(keyword, page=page)

                if not results:
                    empty_count += 1
                    page += 1
                    self._random_delay(1, 2)
                    continue

                empty_count = 0
                valid_count = 0

                for poi in results:
                    uid = poi.get('uid', '') or f"{poi['name']}_{poi['lng']}_{poi['lat']}"
                    lng = poi.get('lng', 0)
                    lat = poi.get('lat', 0)

                    if uid not in poi_uids and lng > 0 and lat > 0:
                        # 检查是否在边界内
                        if self.is_in_boundary(lng, lat):
                            poi_uids.add(uid)

                            # 转换坐标
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
                            category_pois.append(poi_data)
                            valid_count += 1

                print(f"  第{page+1}页: 获取{len(results)}条, 边界内{valid_count}条")

                page += 1
                self._random_delay(1.5, 3)

            self._random_delay(2, 4)

        print(f"\n{category_name} 共爬取到 {len(category_pois)} 条数据")
        return category_pois

    def crawl_all_categories(self, categories):
        """爬取所有类别"""
        print(f"\n开始爬取鼓楼区POI数据")
        print(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        all_results = []
        summary = {}

        for category_name, keywords in categories.items():
            pois = self.crawl_category(category_name, keywords)
            all_results.extend(pois)
            summary[category_name] = len(pois)

            # 每个类别之间休息一下
            self._random_delay(3, 5)

        self.total_results = all_results

        print(f"\n{'='*50}")
        print("爬取完成！数据汇总：")
        print(f"{'='*50}")
        for category, count in summary.items():
            print(f"{category}: {count}条")
        print(f"总计: {len(all_results)}条")

        return all_results

    def save_results(self, filename_prefix="gulou_poi_crawled"):
        """保存结果"""
        if not self.total_results:
            print("没有数据可保存")
            return

        base_path = r"c:\Users\邱煜\Desktop\地理ai\生活区"

        # 保存Excel
        df = pd.DataFrame(self.total_results)
        excel_path = f"{base_path}\\{filename_prefix}.xlsx"
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"\n数据已保存到Excel: {excel_path}")

        # 保存CSV
        csv_path = f"{base_path}\\{filename_prefix}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"数据已保存到CSV: {csv_path}")

        # 保存JSON
        json_path = f"{base_path}\\{filename_prefix}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.total_results, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到JSON: {json_path}")


# ==================== 主程序 ====================

# 八大类POI关键词
POI_CATEGORIES = {
    "餐饮设施": ["餐厅", "饭店", "快餐", "小吃", "面馆", "火锅", "烧烤", "甜品", "咖啡", "奶茶", "蛋糕店", "早餐店"],
    "超市商场": ["超市", "商场", "便利店", "购物中心", "百货", "菜市场", "水果店"],
    "医疗设施": ["医院", "诊所", "卫生院", "药店", "药房", "社区卫生"],
    "教育设施": ["幼儿园", "小学", "中学", "大学", "学校", "培训机构", "教育"],
    "公园广场": ["公园", "广场", "绿地", "游园", "花园"],
    "交通设施": ["地铁站", "公交站", "停车场", "加油站"],
    "金融设施": ["银行", "ATM", "信用社", "证券"],
    "休闲娱乐设施": ["电影院", "KTV", "健身房", "体育馆", "游泳馆", "网吧", "棋牌室", "酒吧"]
}


def main():
    """主函数"""
    geojson_path = r"c:\Users\邱煜\Desktop\地理ai\生活区\鼓楼区.geojson"

    # 创建爬虫实例
    crawler = BaiduPOICrawler(geojson_path)

    # 爬取所有类别
    crawler.crawl_all_categories(POI_CATEGORIES)

    # 保存结果
    crawler.save_results()

    print("\n所有任务完成！")


if __name__ == "__main__":
    main()
