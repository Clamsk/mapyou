#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
坐标转换脚本：BD-09（百度坐标）转 WGS-84（GPS坐标）
用于将百度地图POI数据转换为ArcGIS Pro可用的标准坐标
"""

import pandas as pd
import math

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


def convert_excel_file(input_file, output_file):
    """
    转换Excel文件中的坐标
    """
    print(f"正在读取文件: {input_file}")
    df = pd.read_excel(input_file)

    # 检查列名，确定经纬度列
    lng_col = None
    lat_col = None

    if '经度' in df.columns:
        lng_col = '经度'
        lat_col = '纬度'
    elif '经度_BD09' in df.columns:
        lng_col = '经度_BD09'
        lat_col = '纬度_BD09'
    else:
        print("错误：未找到经纬度列")
        return

    print(f"原始坐标列: {lng_col}, {lat_col}")
    print(f"数据总条数: {len(df)}")

    # 转换坐标
    print("正在转换坐标 BD-09 -> WGS-84...")
    wgs_coords = df.apply(
        lambda row: bd09_to_wgs84(row[lng_col], row[lat_col]),
        axis=1
    )

    df['经度_WGS84'] = [coord[0] for coord in wgs_coords]
    df['纬度_WGS84'] = [coord[1] for coord in wgs_coords]

    # 四舍五入到6位小数
    df['经度_WGS84'] = df['经度_WGS84'].round(6)
    df['纬度_WGS84'] = df['纬度_WGS84'].round(6)

    # 重命名原始列
    if lng_col == '经度':
        df = df.rename(columns={'经度': '经度_BD09', '纬度': '纬度_BD09'})

    # 保存结果
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"转换完成！已保存到: {output_file}")

    # 显示转换示例
    print("\n转换示例（前3条）:")
    sample = df[['名称', '经度_BD09', '纬度_BD09', '经度_WGS84', '纬度_WGS84']].head(3)
    print(sample.to_string(index=False))

    return df


def main():
    """主函数"""
    base_path = r"c:\Users\邱煜\Desktop\地理ai\生活区"

    # 转换已有的POI数据
    input_file = f"{base_path}\\gulou_poi_all.xlsx"
    output_file = f"{base_path}\\gulou_poi_all_wgs84.xlsx"

    try:
        df = convert_excel_file(input_file, output_file)

        # 同时保存CSV版本（方便ArcGIS导入）
        csv_output = f"{base_path}\\gulou_poi_all_wgs84.csv"
        df.to_csv(csv_output, index=False, encoding='utf-8-sig')
        print(f"CSV版本已保存到: {csv_output}")

        print("\n" + "="*50)
        print("在 ArcGIS Pro 中导入说明：")
        print("="*50)
        print("1. 打开 ArcGIS Pro，点击 Map -> Add Data -> XY Point Data")
        print("2. 选择导出的 CSV 或 Excel 文件")
        print("3. X Field 选择: 经度_WGS84")
        print("4. Y Field 选择: 纬度_WGS84")
        print("5. Coordinate System 选择: GCS_WGS_1984 (EPSG:4326)")
        print("6. 点击 OK 即可正确显示POI点位")

    except FileNotFoundError:
        print(f"错误：找不到文件 {input_file}")
        print("请先运行 get_gulou_poi_test.py 采集数据")


if __name__ == "__main__":
    main()
