"""
社区 8 类设施便利度与多样性计算（基于直线距离）

- 输入：
  * 社区中心点 Excel：生活区/社区poi/*.xlsx
    列名：区域/区县、名称/小区、经度_WGS84、纬度_WGS84
  * 设施 POI Excel：生活区/设施poi/*.xlsx
    列名：类别、名称、经度_WGS84、纬度_WGS84
- 距离：WGS84 球面距离（Haversine，米）
- 输出：输出/社区便利度多样性_直线.xlsx
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

# =========================================================
# 参数区
# =========================================================

import os
BASE_DIR = Path(os.environ.get("MAPYOU_DATA_DIR", str(Path(__file__).resolve().parent)))

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

def haversine_vectorized(lon1, lat1, lon2_arr, lat2_arr):
    """
    计算一个点到多个点的球面距离（米）。

    Args:
        lon1, lat1: 单个点的经纬度
        lon2_arr, lat2_arr: numpy数组，多个点的经纬度

    Returns:
        numpy数组，每个距离（米）
    """
    lon1 = np.radians(lon1)
    lat1 = np.radians(lat1)
    lon2_arr = np.radians(lon2_arr)
    lat2_arr = np.radians(lat2_arr)

    dlon = lon2_arr - lon1
    dlat = lat2_arr - lat1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2_arr) * np.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * np.arcsin(np.sqrt(a))


def load_communities(folder: Path) -> pd.DataFrame:
    """加载所有社区文件"""
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
    """加载所有设施POI文件"""
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


def compute_scores_haversine(
    comm: pd.DataFrame,
    pois: pd.DataFrame,
    radii: dict[str, float],
    default_r: float
) -> pd.DataFrame:
    """计算每个社区的便利度和多样性"""

    categories = sorted(pois["category"].unique())
    print(f"\n类别: {categories}")

    # 按类别分组设施
    cat_map = {c: pois[pois["category"] == c] for c in categories}

    results = []
    total = len(comm)

    for idx, row in comm.iterrows():
        rec = {
            "区域": row["region"],
            "社区名称": row["name"],
            "经度": row["lng"],
            "纬度": row["lat"],
        }

        lng, lat = row["lng"], row["lat"]
        diversity = 0

        # 计算每个类别的便利度
        for cat in categories:
            r = radii.get(cat, default_r)
            cdf = cat_map[cat]

            # 计算距离
            dist = haversine_vectorized(lng, lat, cdf["lng"].values, cdf["lat"].values)

            # 统计在半径内的设施数量
            count = int((dist <= r).sum())
            rec[f"{cat}_便利度"] = count

            if count > 0:
                diversity += 1

        rec["多样性"] = diversity
        results.append(rec)

        if (idx + 1) % 500 == 0:
            print(f"  已完成 {idx + 1} / {total} 个社区")

    return pd.DataFrame(results)


# =========================================================
# 主流程
# =========================================================

def main():
    comm_dir = BASE_DIR / "社区poi"
    poi_dir = BASE_DIR / "设施poi"
    out_dir = BASE_DIR / "输出"
    out_dir.mkdir(exist_ok=True)

    # 缓存文件路径
    cache_comm_file = out_dir / "缓存_总社区poi.xlsx"
    cache_poi_file = out_dir / "缓存_总设施poi.xlsx"

    print("=" * 60)
    print("社区设施便利度与多样性分析（直线距离版）")
    print("=" * 60)

    # 读取或加载社区数据
    print("\n[1/4] 读取社区数据...")
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
    print("\n[2/4] 读取设施 POI...")
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

    print("\n[3/4] 开始计算便利度与多样性...")
    print(f"  使用半径配置:")
    for cat, r in sorted(radius_dict.items()):
        print(f"    {cat}: {r} 米")
    print(f"    其他: {default_radius} 米")

    result = compute_scores_haversine(
        communities, pois, radius_dict, default_radius
    )

    print("\n[4/4] 保存结果...")
    out_file = out_dir / "社区便利度多样性_直线.xlsx"
    result.to_excel(out_file, index=False)

    print("=" * 60)
    print(f"[OK] 计算完成！结果已保存至:")
    print(f"  {out_file}")
    print("=" * 60)

    # 打印统计信息
    print("\n统计摘要:")
    print(f"  总社区数: {len(result)}")
    print(f"  平均多样性: {result['多样性'].mean():.2f}")
    print(f"  多样性分布:")
    for i in range(9):
        count = (result['多样性'] == i).sum()
        pct = count / len(result) * 100
        print(f"    {i} 类: {count} 个 ({pct:.1f}%)")


if __name__ == "__main__":
    main()
