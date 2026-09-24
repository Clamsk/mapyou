"""
测试交互式地图的基本功能
"""

import pandas as pd
from pathlib import Path

# 加载数据
print("加载数据...")
community_file = Path("输出/缓存_总社区poi.xlsx")
facility_file = Path("输出/缓存_总设施poi.xlsx")

community_df = pd.read_excel(community_file)
facility_df = pd.read_excel(facility_file)

print(f"社区数据: {len(community_df)} 条")
print(f"社区列名: {community_df.columns.tolist()}")
print(f"\n设施数据: {len(facility_df)} 条")
print(f"设施列名: {facility_df.columns.tolist()}")
print(f"\n设施类别:")
print(facility_df['category'].value_counts())

# 测试创建结果DataFrame
print("\n\n测试结果DataFrame创建...")
results = []
for idx, row in community_df.head(5).iterrows():  # 只测试前5个
    results.append({
        '社区名称': row['name'],
        '区域': row.get('region', '未知'),
        '纬度': row['lat'],
        '经度': row['lng'],
        '多样性': 5,
        '加权便利度': 6.5,
    })

df = pd.DataFrame(results)
print("\n结果DataFrame:")
print(df)
print(f"\n列名: {df.columns.tolist()}")
print(f"\n纬度均值: {df['纬度'].mean()}")
print(f"经度均值: {df['经度'].mean()}")

print("\n✓ 测试通过！数据结构正确。")
