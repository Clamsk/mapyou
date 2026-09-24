"""测试路网加载功能"""
from pathlib import Path
import geopandas as gpd

shp_file = Path(__file__).resolve().parent / "OSM福建" / "gis_osm_roads_free_1.shp"

print("读取路网shp文件...")
# 只读取前10条测试
roads = gpd.read_file(shp_file, rows=10)

print(f"成功读取 {len(roads)} 条道路")
print(f"坐标系: {roads.crs}")
print(f"列名: {roads.columns.tolist()}")
print(f"\n前3条数据:")
print(roads[['fclass', 'name', 'geometry']].head(3))

print("\n检查可用的fclass类型:")
roads_full = gpd.read_file(shp_file)
print(f"总共 {len(roads_full)} 条道路")
print(f"fclass类型: {sorted(roads_full['fclass'].unique())}")
