"""
社区设施便利度与多样性计算（基于弗劳德数的不同腿长分析）

基于弗劳德数（Froude Number）计算不同腿长下的步行速度：
- FS = √(L·g)
- TPWS = 0.42 × FS
- 其中 L 为腿长（米），g = 9.82 m/s²

计算15分钟步行距离作为统一阈值：
- 阈值距离 = TPWS × 15 × 60（米）

- 输入：
  * 社区中心点 Excel：生活区/社区poi/*.xlsx
  * 设施 POI Excel：生活区/设施poi/*.xlsx
- 距离：OSM 步行路网最短路径（米）
- 输出：输出/设施便利度_弗劳德数_腿长{L}m.xlsx（每个腿长一个文件）
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
# 参数区
# =========================================================

import os
BASE_DIR = Path(os.environ.get("MAPYOU_DATA_DIR", str(Path(__file__).resolve().parent)))
OSM_ROAD_SHP = BASE_DIR / "OSM福建" / "gis_osm_roads_free_1.shp"
GRAPH_CACHE = BASE_DIR / "输出" / "缓存_路网图.gpickle"

# 弗劳德数参数
GRAVITY = 9.82  # 重力加速度 m/s²
FROUDE_COEF = 0.42  # 弗劳德系数
WALK_TIME_MINUTES = 15  # 步行时间（分钟）

# 腿长系列（米）：从0.5米到1.2米
LEG_LENGTHS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]

# =========================================================
# 工具函数
# =========================================================

def calculate_walking_speed(leg_length: float) -> float:
    """
    根据弗劳德数计算步行速度

    Args:
        leg_length: 腿长（米）

    Returns:
        步行速度（米/秒）
    """
    FS = np.sqrt(leg_length * GRAVITY)
    TPWS = FROUDE_COEF * FS
    return TPWS


def calculate_walking_distance(leg_length: float, time_minutes: float) -> float:
    """
    计算给定时间内的步行距离

    Args:
        leg_length: 腿长（米）
        time_minutes: 步行时间（分钟）

    Returns:
        步行距离（米）
    """
    speed = calculate_walking_speed(leg_length)
    distance = speed * time_minutes * 60  # 转换为秒
    return distance


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
    """从本地OSM shp文件构建路网图"""
    if cache_file.exists():
        print(f"  发现缓存路网图: {cache_file.name}")
        with open(cache_file, 'rb') as f:
            G = pickle.load(f)
        print(f"  已加载: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
        return G

    print(f"  从shp构建路网图: {shp_file.name}")
    roads = gpd.read_file(shp_file, bbox=bbox)
    print(f"  读取到 {len(roads)} 条道路")

    # 筛选步行可用道路
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
    node_map = {}

    for idx, row in roads.iterrows():
        geom = row.geometry
        if geom.geom_type != 'LineString':
            continue

        coords = list(geom.coords)
        for i in range(len(coords) - 1):
            p1, p2 = coords[i], coords[i + 1]

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

    nodes = list(G.nodes())
    node_coords = np.array([[G.nodes[n]['x'], G.nodes[n]['y']] for n in nodes])

    tree = cKDTree(node_coords)

    points = np.column_stack([lons, lats])
    distances, indices = tree.query(points)

    return np.array([nodes[i] for i in indices])


def compute_scores_for_leg_length(
    comm: pd.DataFrame,
    pois: pd.DataFrame,
    leg_length: float,
    walk_threshold: float,
    G
) -> pd.DataFrame:
    """
    计算特定腿长下的便利度和多样性

    Args:
        comm: 社区数据
        pois: 设施POI数据
        leg_length: 腿长（米）
        walk_threshold: 步行阈值距离（米）
        G: 路网图

    Returns:
        结果DataFrame
    """
    categories = sorted(pois["category"].unique())
    cat_map = {c: pois[pois["category"] == c] for c in categories}

    results = []

    # 第一遍：收集所有数据
    raw_results = []

    for idx, row in comm.iterrows():
        rec = {
            "区域": row["region"],
            "社区名称": row["name"],
            "经度": row["lng"],
            "纬度": row["lat"],
            "腿长_米": leg_length,
            "步行速度_米每秒": calculate_walking_speed(leg_length),
            "15分钟步行距离_米": walk_threshold,
        }

        src = row["node"]
        diversity = 0

        for cat in categories:
            # 使用统一的步行阈值
            lengths = nx.single_source_dijkstra_path_length(
                G,
                source=src,
                cutoff=walk_threshold,
                weight="length"
            )

            count = sum(1 for n in cat_map[cat]["node"].values if n in lengths)
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

        if (idx + 1) % 500 == 0:
            print(f"    已完成 {idx + 1} / {len(comm)} 个社区")

    # 第二遍：计算每类设施的最大值
    df_temp = pd.DataFrame(raw_results)
    max_values = {}
    for cat in categories:
        col_name = f"{cat}_便利度"
        max_val = df_temp[col_name].max()
        max_values[cat] = max_val if max_val > 0 else 1

    # 第三遍：计算总便利度
    for rec in raw_results:
        normalized_scores = []
        for cat in categories:
            col_name = f"{cat}_便利度"
            normalized = rec[col_name] / max_values[cat]
            normalized_scores.append(normalized)

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

    print("=" * 80)
    print("社区设施便利度分析（基于弗劳德数的不同腿长分析）")
    print("=" * 80)

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

    # 计算边界框
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

    # 打印弗劳德数参数表
    print("\n" + "=" * 80)
    print("弗劳德数参数配置:")
    print(f"  重力加速度 g = {GRAVITY} m/s²")
    print(f"  弗劳德系数 = {FROUDE_COEF}")
    print(f"  步行时间 = {WALK_TIME_MINUTES} 分钟")
    print("\n腿长与步行参数对照表:")
    print(f"{'腿长(m)':<10} {'FS值':<10} {'步行速度(m/s)':<15} {'15分钟距离(m)':<15}")
    print("-" * 80)

    for L in LEG_LENGTHS:
        FS = np.sqrt(L * GRAVITY)
        speed = FROUDE_COEF * FS
        distance = speed * WALK_TIME_MINUTES * 60
        print(f"{L:<10.2f} {FS:<10.2f} {speed:<15.2f} {distance:<15.0f}")

    print("=" * 80)

    # 对每个腿长进行分析
    print(f"\n[5/5] 开始计算不同腿长下的便利度...")
    print(f"  共计算 {len(LEG_LENGTHS)} 个腿长参数\n")

    all_results = []

    for i, leg_length in enumerate(LEG_LENGTHS, 1):
        walk_distance = calculate_walking_distance(leg_length, WALK_TIME_MINUTES)
        walk_speed = calculate_walking_speed(leg_length)

        print(f"  [{i}/{len(LEG_LENGTHS)}] 腿长 {leg_length} 米:")
        print(f"    步行速度: {walk_speed:.2f} m/s")
        print(f"    15分钟步行距离: {walk_distance:.0f} 米")

        result = compute_scores_for_leg_length(
            communities, pois, leg_length, walk_distance, G
        )

        # 保存单独的结果文件
        out_file = out_dir / f"设施便利度_弗劳德数_腿长{leg_length:.2f}m.xlsx"
        result.to_excel(out_file, index=False)
        print(f"    已保存: {out_file.name}")

        # 添加到汇总结果
        all_results.append(result)

        # 打印简要统计
        avg_diversity = result['多样性'].mean()
        avg_comprehensive = result['综合便利度'].mean()
        avg_total = result['总便利度'].mean()
        full_access = (result['多样性'] == 8).sum()
        print(f"    平均多样性: {avg_diversity:.2f}")
        print(f"    平均综合便利度: {avg_comprehensive:.2f}")
        print(f"    平均总便利度: {avg_total:.2f} / 8.00")
        print(f"    全部8类可达: {full_access} 个社区 ({full_access/len(result)*100:.1f}%)\n")

    # 合并所有结果
    print("\n正在生成汇总报告...")
    combined = pd.concat(all_results, ignore_index=True)
    summary_file = out_dir / "设施便利度_弗劳德数_汇总.xlsx"
    combined.to_excel(summary_file, index=False)

    # 生成对比分析表
    print("正在生成对比分析表...")

    # 动态获取所有便利度列名
    facility_cols = [col for col in combined.columns if col.endswith('_便利度')]

    comparison_data = []
    for leg_length in LEG_LENGTHS:
        df_leg = combined[combined['腿长_米'] == leg_length]
        row_data = {
            '腿长_米': leg_length,
            '步行速度_米每秒': df_leg['步行速度_米每秒'].iloc[0],
            '15分钟步行距离_米': df_leg['15分钟步行距离_米'].iloc[0],
            '平均多样性': df_leg['多样性'].mean(),
            '多样性标准差': df_leg['多样性'].std(),
            '平均综合便利度': df_leg['综合便利度'].mean(),
            '综合便利度标准差': df_leg['综合便利度'].std(),
            '平均总便利度': df_leg['总便利度'].mean(),
            '总便利度标准差': df_leg['总便利度'].std(),
            '全部8类可达_社区数': (df_leg['多样性'] == 8).sum(),
            '全部8类可达_百分比': (df_leg['多样性'] == 8).sum() / len(df_leg) * 100,
        }

        # 动态添加各类设施的平均便利度
        for col in facility_cols:
            category_name = col.replace('_便利度', '')
            row_data[f'平均{category_name}便利度'] = df_leg[col].mean()

        comparison_data.append(row_data)

    comparison_df = pd.DataFrame(comparison_data)
    comparison_file = out_dir / "设施便利度_弗劳德数_对比分析.xlsx"
    comparison_df.to_excel(comparison_file, index=False)

    print("\n" + "=" * 80)
    print("[OK] 计算完成！结果文件:")
    print(f"  汇总数据: {summary_file}")
    print(f"  对比分析: {comparison_file}")
    print(f"  各腿长详细数据: {len(LEG_LENGTHS)} 个文件")
    print("=" * 80)

    # 打印最终统计摘要
    print("\n统计摘要（按腿长）:")
    print(comparison_df[['腿长_米', '15分钟步行距离_米', '平均多样性', '全部8类可达_百分比']].to_string(index=False))


if __name__ == "__main__":
    main()
