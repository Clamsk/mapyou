"""
社区 8 类设施便利度与多样性计算（基于真实步行路网距离）

- 输入：
  * 社区中心点 Excel：生活区/社区poi/*.xlsx
    列名：区域/区县、名称/小区、经度_WGS84、纬度_WGS84
  * 设施 POI Excel：生活区/设施poi/*.xlsx
    列名：类别、名称、经度_WGS84、纬度_WGS84
- 距离：OSM 步行路网最短路径（米）
- 输出：输出/社区便利度多样性_路网.xlsx
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString

# =========================================================
# 参数区（你只需改这里）
# =========================================================

import os
BASE_DIR = Path(os.environ.get("MAPYOU_DATA_DIR", str(Path(__file__).resolve().parent)))
OSM_ROAD_SHP = BASE_DIR / "OSM福建" / "gis_osm_roads_free_1.shp"
GRAPH_CACHE = BASE_DIR / "输出" / "缓存_路网图.gpickle"

# 不同设施的步行阈值（米），未列出的用 default_radius
radius_dict = {
    "餐饮设施": 1000,
    "超市商场": 1000,
    "医疗设施": 1200,
    "教育设施": 1500,
    "交通设施": 800,
    "体育休闲设施": 1200,
    "公园广场": 1500,
    "便民服务": 800,
}
default_radius = 1000  # 米

# =========================================================
# 工具函数
# =========================================================

def load_communities(folder: Path) -> pd.DataFrame:
    dfs = []
    for f in folder.glob("*.xlsx"):
        print(f"  加载社区: {f.name}")
        df = pd.read_excel(f)
        df = df.rename(columns={
            "经度_WGS84": "lng",
            "纬度_WGS84": "lat",
            "经度": "lng",
            "纬度": "lat",
            "名称": "name",
            "小区": "name",
            "区域": "region",
            "区县": "region",
        })
        if not {"lng", "lat", "name"}.issubset(df.columns):
            raise ValueError(f"社区文件缺列: {f.name}")
        if "region" not in df.columns:
            df["region"] = f.stem
        df = df[["region", "name", "lng", "lat"]]
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError("未找到社区 poi 文件")

    return pd.concat(dfs, ignore_index=True)


def load_pois(folder: Path) -> pd.DataFrame:
    dfs = []
    for f in folder.glob("*.xlsx"):
        print(f"  加载设施: {f.name}")
        df = pd.read_excel(f)
        df = df.rename(columns={
            "经度_WGS84": "lng",
            "纬度_WGS84": "lat",
            "经度": "lng",
            "纬度": "lat",
            "名称": "name",
            "类别": "category",
        })
        if not {"lng", "lat", "name", "category"}.issubset(df.columns):
            raise ValueError(f"设施文件缺列: {f.name}")
        df = df[["category", "name", "lng", "lat"]]
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError("未找到设施 poi 文件")

    pois = pd.concat(dfs, ignore_index=True)
    pois = pois.drop_duplicates(subset=["category", "name", "lng", "lat"])
    return pois


def load_graph_from_shp(shp_file: Path, cache_file: Path, bbox=None):
    """从本地OSM shp文件构建路网图

    Args:
        shp_file: OSM道路shp文件路径
        cache_file: 缓存的图文件路径
        bbox: 边界框 (minx, miny, maxx, maxy)，None则使用全部
    """
    if cache_file.exists():
        print(f"  发现缓存路网图: {cache_file.name}")
        with open(cache_file, 'rb') as f:
            G = pickle.load(f)
        print(f"  已加载: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
        return G

    print(f"  从shp构建路网图: {shp_file.name}")
    roads = gpd.read_file(shp_file, bbox=bbox)
    print(f"  读取到 {len(roads)} 条道路")

    # 筛选步行可用道路（排除高速等）
    walk_types = ['footway', 'path', 'pedestrian', 'steps', 'residential',
                  'living_street', 'service', 'unclassified', 'tertiary',
                  'secondary', 'primary', 'track']
    if 'fclass' in roads.columns:
        roads = roads[roads['fclass'].isin(walk_types)]
        print(f"  筛选步行道路: {len(roads)} 条")

    # 转换为WGS84
    if roads.crs != 'EPSG:4326':
        roads = roads.to_crs('EPSG:4326')

    # 构建networkx图
    G = nx.Graph()
    node_id = 0
    node_map = {}  # (lon, lat) -> node_id

    for idx, row in roads.iterrows():
        geom = row.geometry
        if geom.geom_type != 'LineString':
            continue

        coords = list(geom.coords)
        for i in range(len(coords) - 1):
            p1, p2 = coords[i], coords[i + 1]

            # 创建或获取节点
            if p1 not in node_map:
                node_map[p1] = node_id
                G.add_node(node_id, x=p1[0], y=p1[1])
                node_id += 1
            if p2 not in node_map:
                node_map[p2] = node_id
                G.add_node(node_id, x=p2[0], y=p2[1])
                node_id += 1

            # 计算边长度（米）
            from math import radians, sin, cos, sqrt, asin
            lon1, lat1 = radians(p1[0]), radians(p1[1])
            lon2, lat2 = radians(p2[0]), radians(p2[1])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            length = 6371000 * 2 * asin(sqrt(a))

            n1, n2 = node_map[p1], node_map[p2]
            G.add_edge(n1, n2, length=length)

    print(f"  构建完成: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
    print(f"  保存缓存: {cache_file.name}")
    cache_file.parent.mkdir(exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(G, f)

    return G


def find_nearest_nodes(G, lons, lats):
    """为每个点找到最近的路网节点"""
    from scipy.spatial import cKDTree

    # 获取所有节点坐标
    nodes = list(G.nodes())
    node_coords = np.array([[G.nodes[n]['x'], G.nodes[n]['y']] for n in nodes])

    # 构建KD树
    tree = cKDTree(node_coords)

    # 查询最近节点
    points = np.column_stack([lons, lats])
    distances, indices = tree.query(points)

    return np.array([nodes[i] for i in indices])


def compute_scores_network(
    comm: pd.DataFrame,
    pois: pd.DataFrame,
    radii: dict[str, float],
    default_r: float,
    G
) -> pd.DataFrame:

    categories = sorted(pois["category"].unique())
    cat_map = {c: pois[pois["category"] == c] for c in categories}

    results = []

    # 第一遏：收集所有数据，用于计算每类的最大值
    raw_results = []

    for idx, row in comm.iterrows():
        rec = {
            "区域": row["region"],
            "社区名称": row["name"],
            "经度": row["lng"],
            "纬度": row["lat"],
        }

        src = row["node"]
        diversity = 0

        for cat in categories:
            r = radii.get(cat, default_r)
            cdf = cat_map[cat]

            # 单源最短路径（限制在 r 米内，提速）
            lengths = nx.single_source_dijkstra_path_length(
                G,
                source=src,
                cutoff=r,
                weight="length"
            )

            count = sum(1 for n in cdf["node"].values if n in lengths)
            rec[f"{cat}_便利度"] = count

            if count > 0:
                diversity += 1

        rec["多样性"] = diversity

        # 计算综合便利度：种类优先，数量辅助
        # 公式：综合便利度 = 多样性 × 100 + 总设施数量的对数
        total_facilities = sum(rec[f"{cat}_便利度"] for cat in categories)
        if total_facilities > 0:
            # 使用对数避免数量差异过大
            quantity_score = np.log10(total_facilities + 1) * 10
        else:
            quantity_score = 0
        rec["综合便利度"] = diversity * 100 + quantity_score

        raw_results.append(rec)

        if (idx + 1) % 100 == 0:
            print(f"  已完成 {idx + 1} / {len(comm)} 个社区")

    # 第二遍：计算每类设施的最大值，用于Min-Max标准化
    df_temp = pd.DataFrame(raw_results)
    max_values = {}
    for cat in categories:
        col_name = f"{cat}_便利度"
        max_val = df_temp[col_name].max()
        max_values[cat] = max_val if max_val > 0 else 1  # 避免除以0

    # 第三遍：计算标准化后的总便利度
    for rec in raw_results:
        # 对每类设施进行Min-Max标准化（0-1）
        normalized_scores = []
        for cat in categories:
            col_name = f"{cat}_便利度"
            normalized = rec[col_name] / max_values[cat]
            normalized_scores.append(normalized)

        # 求和得到总便利度（0-8分）
        rec["总便利度"] = sum(normalized_scores)
        results.append(rec)

    return pd.DataFrame(results)


# =========================================================
# 主流程
# =========================================================

def main():
    comm_dir = BASE_DIR / "社区poi"
    poi_dir = BASE_DIR / "设施poi"
    out_dir = BASE_DIR / "输出"
    out_dir.mkdir(exist_ok=True)

    # 缓存文件
    cache_comm_file = out_dir / "缓存_总社区poi.xlsx"
    cache_poi_file = out_dir / "缓存_总设施poi.xlsx"

    print("=" * 60)
    print("社区设施便利度与多样性分析（路网距离版）")
    print("=" * 60)

    # 读取或加载社区数据
    print("\n[1/5] 读取社区数据...")
    if cache_comm_file.exists():
        print(f"  发现缓存文件，直接加载: {cache_comm_file.name}")
        communities = pd.read_excel(cache_comm_file)
        print(f"  共加载 {len(communities)} 个社区")
    else:
        print("  未找到缓存，重新读取原始文件...")
        communities = load_communities(comm_dir)
        print(f"  共加载 {len(communities)} 个社区")
        print(f"  保存到缓存: {cache_comm_file.name}")
        communities.to_excel(cache_comm_file, index=False)

    # 读取或加载设施POI
    print("\n[2/5] 读取设施 POI...")
    if cache_poi_file.exists():
        print(f"  发现缓存文件，直接加载: {cache_poi_file.name}")
        pois = pd.read_excel(cache_poi_file)
        print(f"  共加载 {len(pois)} 个设施POI")
        print(f"  类别数量: {pois['category'].nunique()}")
    else:
        print("  未找到缓存，重新读取原始文件...")
        pois = load_pois(poi_dir)
        print(f"  共加载 {len(pois)} 个设施POI")
        print(f"  类别数量: {pois['category'].nunique()}")
        print(f"  保存到缓存: {cache_poi_file.name}")
        pois.to_excel(cache_poi_file, index=False)

    print("\n[3/5] 加载步行路网...")
    if not OSM_ROAD_SHP.exists():
        raise FileNotFoundError(f"路网文件不存在: {OSM_ROAD_SHP}")

    # 计算福州区域边界框（根据社区和POI范围）
    all_lons = list(communities['lng']) + list(pois['lng'])
    all_lats = list(communities['lat']) + list(pois['lat'])
    bbox = (
        min(all_lons) - 0.1, min(all_lats) - 0.1,
        max(all_lons) + 0.1, max(all_lats) + 0.1
    )
    print(f"  数据范围: {bbox}")

    G = load_graph_from_shp(OSM_ROAD_SHP, GRAPH_CACHE, bbox=bbox)

    print("\n[4/5] 匹配POI到最近路网节点...")
    print("  匹配社区...")
    communities["node"] = find_nearest_nodes(
        G, communities["lng"].values, communities["lat"].values
    )
    print("  匹配设施...")
    pois["node"] = find_nearest_nodes(
        G, pois["lng"].values, pois["lat"].values
    )

    print("\n[5/5] 开始计算便利度与多样性（路网距离）...")
    print(f"  使用半径配置:")
    for cat, r in sorted(radius_dict.items()):
        print(f"    {cat}: {r} 米")
    print(f"    其他: {default_radius} 米")

    result = compute_scores_network(
        communities, pois, radius_dict, default_radius, G
    )

    out_file = out_dir / "社区便利度多样性_路网.xlsx"
    result.to_excel(out_file, index=False)

    print("\n" + "=" * 60)
    print(f"[OK] 计算完成！结果已保存至:")
    print(f"  {out_file}")
    print("=" * 60)

    # 统计信息
    print("\n统计摘要:")
    print(f"  总社区数: {len(result)}")
    print(f"  平均多样性: {result['多样性'].mean():.2f}")
    print(f"  平均综合便利度: {result['综合便利度'].mean():.2f}")
    print(f"  平均总便利度: {result['总便利度'].mean():.2f} / 8.00")
    print(f"  综合便利度范围: {result['综合便利度'].min():.2f} ~ {result['综合便利度'].max():.2f}")
    print(f"  总便利度范围: {result['总便利度'].min():.2f} ~ {result['总便利度'].max():.2f}")
    print(f"\n  多样性分布:")
    for i in range(9):
        count = (result['多样性'] == i).sum()
        pct = count / len(result) * 100
        print(f"    {i} 类: {count} 个 ({pct:.1f}%)")


if __name__ == "__main__":
    main()
