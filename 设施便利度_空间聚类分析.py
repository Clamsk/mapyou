"""
设施便利度地理空间聚类分析

对每个腿长的结果进行空间聚类分析，识别不同便利度等级的空间分布：
- 高便利度区域：多样性≥7，适合居住
- 中等便利度区域：4≤多样性<7，基本满足
- 低便利度区域：多样性<4，不太适合

输出：
- 每个腿长的交互式地图（HTML）
- 聚类分析报告（Excel）
- 空间热力图
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns

# =========================================================
# 参数配置
# =========================================================

import os
BASE_DIR = Path(os.environ.get("MAPYOU_DATA_DIR", str(Path(__file__).resolve().parent)))
OUTPUT_DIR = BASE_DIR / "输出"
MAP_DIR = OUTPUT_DIR / "便利度地图"
MAP_DIR.mkdir(exist_ok=True)

# 腿长系列
LEG_LENGTHS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]

# 便利度等级分类
def classify_accessibility(diversity):
    """根据多样性分类便利度等级"""
    if diversity >= 7:
        return '高便利度'
    elif diversity >= 4:
        return '中等便利度'
    else:
        return '低便利度'


def classify_color(diversity):
    """根据多样性返回颜色"""
    if diversity >= 7:
        return 'green'
    elif diversity >= 4:
        return 'orange'
    else:
        return 'red'


# =========================================================
# 空间聚类分析
# =========================================================

def spatial_clustering(df: pd.DataFrame, eps_km=0.5, min_samples=10):
    """
    使用DBSCAN进行空间聚类

    Args:
        df: 包含经纬度和便利度的DataFrame
        eps_km: 邻域半径（公里）
        min_samples: 最小样本数

    Returns:
        添加了聚类标签的DataFrame
    """
    # 准备数据：经纬度 + 多样性
    X = df[['经度', '纬度', '多样性']].copy()

    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # DBSCAN聚类（eps需要根据经纬度尺度调整）
    # 1度经度约等于111km，eps_km/111作为eps
    eps_degree = eps_km / 111.0

    # 对经纬度使用较大的eps，对多样性使用较小的权重
    X_weighted = X_scaled.copy()
    X_weighted[:, 0] *= 1.0  # 经度权重
    X_weighted[:, 1] *= 1.0  # 纬度权重
    X_weighted[:, 2] *= 0.5  # 多样性权重降低，主要按地理位置聚类

    clustering = DBSCAN(eps=eps_degree*10, min_samples=min_samples)
    df['聚类标签'] = clustering.fit_predict(X_weighted)

    return df


# =========================================================
# 地图可视化
# =========================================================

def create_accessibility_map(df: pd.DataFrame, leg_length: float, output_file: Path):
    """
    创建便利度交互式地图

    Args:
        df: 社区数据
        leg_length: 腿长
        output_file: 输出HTML文件路径
    """
    print(f"    [1/5] 计算地图中心点...")
    # 计算中心点
    center_lat = df['纬度'].mean()
    center_lon = df['经度'].mean()

    print(f"    [2/5] 创建地图基础图层...")
    # 创建地图
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )

    # 添加标题
    title_html = f'''
    <div style="position: fixed;
                top: 10px; left: 50px; width: 600px; height: 180px;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:14px; padding: 10px">
        <b style="font-size:16px">设施便利度空间分布图</b><br>
        腿长: {leg_length} 米 | 平均多样性: {df['多样性'].mean():.2f}<br>
        平均综合便利度: {df['综合便利度'].mean():.2f} | 平均总便利度: {df['总便利度'].mean():.2f}/8.00<br>
        <hr style="margin: 5px 0;">
        <b>多样性等级：</b><br>
        <span style="color:green">●</span> 高便利度 (≧ 7类): {(df['多样性']>=7).sum()} 个
        <span style="color:orange">●</span> 中等 (4-6类): {((df['多样性']>=4)&(df['多样性']<7)).sum()} 个
        <span style="color:red">●</span> 低 (<4类): {(df['多样性']<4).sum()} 个<br>
        <hr style="margin: 5px 0;">
        <b>地图说明：</b><br>
        <span style="background-color:#ddd; padding:2px 5px; border-radius:10px; font-size:12px">数字圈</span> = 社区簇（颜色表示密度，点击展开查看单个社区）<br>
        左侧图层控制可切换显示不同便利度等级 | 点击单个社区查看详细指标
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

    print(f"    [3/5] 添加社区标记点 (共{len(df)}个)...")
    # 按便利度等级分组添加标记
    total_markers = 0
    for level, color in [('高便利度', 'green'), ('中等便利度', 'orange'), ('低便利度', 'red')]:
        df_level = df[df['便利度等级'] == level]

        # 创建标记簇
        marker_cluster = MarkerCluster(name=level).add_to(m)

        for idx, row in df_level.iterrows():
            total_markers += 1
            if total_markers % 500 == 0:
                print(f"      已添加 {total_markers}/{len(df)} 个标记...")
            # 创建弹窗内容
            popup_html = f"""
            <div style="font-family: Arial; font-size: 12px;">
                <b>{row['社区名称']}</b><br>
                区域: {row['区域']}<br>
                <hr style="margin: 5px 0;">
                <b>便利度指标：</b><br>
                多样性: {row['多样性']}/8<br>
                综合便利度: {row['综合便利度']:.2f}<br>
                总便利度: {row['总便利度']:.2f}/8.00<br>
                <hr style="margin: 5px 0;">
                <b>各类设施便利度：</b><br>
            """

            # 添加各类设施便利度
            facility_cols = [col for col in df.columns if col.endswith('_便利度')]
            for col in facility_cols:
                category = col.replace('_便利度', '')
                popup_html += f"{category}: {int(row[col])}<br>"

            popup_html += "</div>"

            folium.CircleMarker(
                location=[row['纬度'], row['经度']],
                radius=5,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.6,
                weight=1
            ).add_to(marker_cluster)

    print(f"    [4/5] 生成便利度热力图...")

    # 1. 多样性热力图 (0-8)
    heat_data_diversity = [[row['纬度'], row['经度'], row['多样性']] for idx, row in df.iterrows()]
    diversity_heatmap = folium.FeatureGroup(name='多样性热力图', show=True)
    HeatMap(heat_data_diversity,
            min_opacity=0.3,
            max_val=8.0,
            radius=15,
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(diversity_heatmap)
    diversity_heatmap.add_to(m)

    # 2. 综合便利度热力图
    heat_data_comprehensive = [[row['纬度'], row['经度'], row['综合便利度']] for idx, row in df.iterrows()]
    comprehensive_heatmap = folium.FeatureGroup(name='综合便利度热力图', show=False)
    HeatMap(heat_data_comprehensive,
            min_opacity=0.3,
            max_val=df['综合便利度'].max(),
            radius=15,
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(comprehensive_heatmap)
    comprehensive_heatmap.add_to(m)

    # 3. 总便利度热力图 (0-8)
    heat_data_total = [[row['纬度'], row['经度'], row['总便利度']] for idx, row in df.iterrows()]
    total_heatmap = folium.FeatureGroup(name='总便利度热力图', show=False)
    HeatMap(heat_data_total,
            min_opacity=0.3,
            max_val=8.0,
            radius=15,
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(total_heatmap)
    total_heatmap.add_to(m)

    # 添加热力图图例
    legend_html = '''
    <div id="heatmap-legend" style="position: fixed;
                bottom: 50px; right: 50px; width: 180px; height: 120px;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:12px; padding: 10px; display: block;">
        <b style="font-size:13px">热力图图例</b><br>
        <div style="margin-top: 5px;">
            <div style="background: linear-gradient(to right, blue, yellow, red);
                        height: 20px; width: 100%; margin: 5px 0;"></div>
            <div style="display: flex; justify-content: space-between; font-size: 10px;">
                <span>低</span>
                <span>中</span>
                <span>高</span>
            </div>
        </div>
        <div id="legend-text" style="margin-top: 10px; font-size: 11px;">
            当前显示: <b>多样性</b><br>
            范围: 0 - 8 类
        </div>
        <div style="margin-top: 5px; font-size: 10px; color: #666;">
            提示：切换热力图图层查看不同指标
        </div>
    </div>

    <script>
    // 监听图层控制变化，动态更新图例文本
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
            var layerControl = document.querySelector('.leaflet-control-layers');
            if (layerControl) {
                layerControl.addEventListener('click', function() {
                    setTimeout(function() {
                        updateLegend();
                    }, 100);
                });
            }
        }, 1000);
    });

    function updateLegend() {
        var legendText = document.getElementById('legend-text');
        var checkboxes = document.querySelectorAll('.leaflet-control-layers-overlays input[type="checkbox"]');

        checkboxes.forEach(function(checkbox) {
            var label = checkbox.nextSibling.textContent.trim();
            if (checkbox.checked && label.includes('热力图')) {
                if (label.includes('多样性')) {
                    legendText.innerHTML = '当前显示: <b>多样性</b><br>范围: 0 - 8 类';
                } else if (label.includes('综合便利度')) {
                    legendText.innerHTML = '当前显示: <b>综合便利度</b><br>范围: 0 - ''' + df['综合便利度'].max().round(0).astype(str) + '''';
                } else if (label.includes('总便利度')) {
                    legendText.innerHTML = '当前显示: <b>总便利度</b><br>范围: 0 - 8.00';
                }
            }
        });
    }
    </script>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # 添加图层控制
    folium.LayerControl(collapsed=False).add_to(m)

    print(f"    [5/5] 保存地图文件 (可能需要几秒钟)...")
    # 保存
    m.save(str(output_file))
    print(f"    ✓ 地图已生成: {output_file.name}")


# =========================================================
# 统计分析
# =========================================================

def analyze_spatial_distribution(df: pd.DataFrame, leg_length: float):
    """
    分析空间分布特征

    Returns:
        分析结果字典
    """
    result = {
        '腿长_米': leg_length,
        '总社区数': len(df),
        '高便利度社区数': (df['多样性'] >= 7).sum(),
        '高便利度占比_%': (df['多样性'] >= 7).sum() / len(df) * 100,
        '中等便利度社区数': ((df['多样性'] >= 4) & (df['多样性'] < 7)).sum(),
        '中等便利度占比_%': ((df['多样性'] >= 4) & (df['多样性'] < 7)).sum() / len(df) * 100,
        '低便利度社区数': (df['多样性'] < 4).sum(),
        '低便利度占比_%': (df['多样性'] < 4).sum() / len(df) * 100,
        '平均多样性': df['多样性'].mean(),
        '多样性标准差': df['多样性'].std(),
    }

    # 按区域统计
    region_stats = df.groupby('区域').agg({
        '多样性': ['mean', 'std', 'count']
    }).round(2)

    # 找出最适合和最不适合的区域
    region_avg = df.groupby('区域')['多样性'].mean().sort_values(ascending=False)
    result['最适合居住区域'] = region_avg.index[0] if len(region_avg) > 0 else 'N/A'
    result['最适合区域平均多样性'] = region_avg.iloc[0] if len(region_avg) > 0 else 0
    result['最不适合居住区域'] = region_avg.index[-1] if len(region_avg) > 0 else 'N/A'
    result['最不适合区域平均多样性'] = region_avg.iloc[-1] if len(region_avg) > 0 else 0

    return result, region_stats


def create_comparison_charts(summary_df: pd.DataFrame, output_dir: Path):
    """
    创建对比图表

    Args:
        summary_df: 汇总统计数据
        output_dir: 输出目录
    """
    # 使用Agg后端避免Qt依赖问题
    import matplotlib
    matplotlib.use('Agg')

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    # 创建图表
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. 不同腿长下的便利度等级分布
    ax1 = axes[0, 0]
    x = summary_df['腿长_米']
    ax1.plot(x, summary_df['高便利度占比_%'], marker='o', label='高便利度', linewidth=2, color='green')
    ax1.plot(x, summary_df['中等便利度占比_%'], marker='s', label='中等便利度', linewidth=2, color='orange')
    ax1.plot(x, summary_df['低便利度占比_%'], marker='^', label='低便利度', linewidth=2, color='red')
    ax1.set_xlabel('腿长 (米)', fontsize=12)
    ax1.set_ylabel('占比 (%)', fontsize=12)
    ax1.set_title('不同腿长下的便利度等级分布', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. 平均多样性趋势
    ax2 = axes[0, 1]
    ax2.plot(x, summary_df['平均多样性'], marker='o', linewidth=2, color='blue')
    ax2.fill_between(x,
                      summary_df['平均多样性'] - summary_df['多样性标准差'],
                      summary_df['平均多样性'] + summary_df['多样性标准差'],
                      alpha=0.3)
    ax2.set_xlabel('腿长 (米)', fontsize=12)
    ax2.set_ylabel('平均多样性', fontsize=12)
    ax2.set_title('平均多样性随腿长变化趋势', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # 3. 高便利度社区数量
    ax3 = axes[1, 0]
    ax3.bar(x, summary_df['高便利度社区数'], color='green', alpha=0.7)
    ax3.set_xlabel('腿长 (米)', fontsize=12)
    ax3.set_ylabel('社区数量', fontsize=12)
    ax3.set_title('高便利度社区数量', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')

    # 4. 最适合/最不适合区域的多样性对比
    ax4 = axes[1, 1]
    width = 0.02
    x_pos = np.arange(len(x))
    ax4.bar(x_pos - width/2, summary_df['最适合区域平均多样性'],
            width, label='最适合区域', color='green', alpha=0.7)
    ax4.bar(x_pos + width/2, summary_df['最不适合区域平均多样性'],
            width, label='最不适合区域', color='red', alpha=0.7)
    ax4.set_xlabel('腿长 (米)', fontsize=12)
    ax4.set_ylabel('平均多样性', fontsize=12)
    ax4.set_title('最适合与最不适合区域对比', fontsize=14, fontweight='bold')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([f'{l:.2f}' for l in x], rotation=45)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    # 保存图表
    chart_file = output_dir / '便利度空间分析_对比图表.png'
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    print(f"\n已生成对比图表: {chart_file.name}")
    plt.close()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 80)
    print("设施便利度地理空间聚类分析")
    print("=" * 80)

    all_summaries = []
    all_region_stats = []

    for i, leg_length in enumerate(LEG_LENGTHS, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(LEG_LENGTHS)}] 分析腿长 {leg_length} 米")
        print(f"{'='*60}")

        # 读取数据
        data_file = OUTPUT_DIR / f"设施便利度_弗劳德数_腿长{leg_length:.2f}m.xlsx"
        if not data_file.exists():
            print(f"  ✗ 文件不存在，跳过: {data_file.name}")
            continue

        print(f"  [1/4] 读取数据文件...")
        df = pd.read_excel(data_file)
        print(f"        共 {len(df)} 个社区")

        print(f"  [2/4] 分类便利度等级...")
        # 添加便利度等级分类
        df['便利度等级'] = df['多样性'].apply(classify_accessibility)
        df['便利度颜色'] = df['多样性'].apply(classify_color)

        # 空间聚类（可选）
        # df = spatial_clustering(df, eps_km=0.5, min_samples=10)

        print(f"  [3/4] 统计分析...")
        # 统计分析
        summary, region_stats = analyze_spatial_distribution(df, leg_length)
        all_summaries.append(summary)

        # 添加区域统计信息
        region_stats_flat = region_stats.reset_index()
        region_stats_flat.columns = ['区域', '平均多样性', '多样性标准差', '社区数量']
        region_stats_flat['腿长_米'] = leg_length
        all_region_stats.append(region_stats_flat)

        print(f"        高便利度: {summary['高便利度社区数']} 个 ({summary['高便利度占比_%']:.1f}%)")
        print(f"        中等便利度: {summary['中等便利度社区数']} 个 ({summary['中等便利度占比_%']:.1f}%)")
        print(f"        低便利度: {summary['低便利度社区数']} 个 ({summary['低便利度占比_%']:.1f}%)")
        print(f"        最适合: {summary['最适合居住区域']} (多样性: {summary['最适合区域平均多样性']:.2f})")
        print(f"        最不适合: {summary['最不适合居住区域']} (多样性: {summary['最不适合区域平均多样性']:.2f})")

        print(f"  [4/4] 创建交互式地图...")
        # 创建地图
        map_file = MAP_DIR / f"便利度地图_腿长{leg_length:.2f}m.html"
        create_accessibility_map(df, leg_length, map_file)

        print(f"    保存带分类标签的数据...")
        # 保存带聚类标签的数据
        output_with_cluster = OUTPUT_DIR / f"设施便利度_带分类_腿长{leg_length:.2f}m.xlsx"
        df.to_excel(output_with_cluster, index=False)
        print(f"    ✓ 完成腿长 {leg_length} 米的分析")

    # 保存汇总统计
    print("\n" + "="*80)
    print("生成汇总报告和图表")
    print("="*80)
    print("\n[1/4] 保存汇总统计...")
    summary_df = pd.DataFrame(all_summaries)
    summary_file = OUTPUT_DIR / "便利度空间分析_汇总统计.xlsx"
    summary_df.to_excel(summary_file, index=False)
    print(f"  ✓ 已保存: {summary_file.name}")

    print("\n[2/4] 保存区域统计...")
    # 保存区域统计
    region_df = pd.concat(all_region_stats, ignore_index=True)
    region_file = OUTPUT_DIR / "便利度空间分析_区域统计.xlsx"
    region_df.to_excel(region_file, index=False)
    print(f"  ✓ 已保存: {region_file.name}")

    print("\n[3/4] 生成对比图表...")
    # 创建对比图表
    create_comparison_charts(summary_df, OUTPUT_DIR)

    print("\n[4/4] 生成建议报告...")
    # 生成建议报告

    # 找出变化最大的区域
    pivot_region = region_df.pivot(index='区域', columns='腿长_米', values='平均多样性')
    region_change = pivot_region.iloc[:, -1] - pivot_region.iloc[:, 0]

    report = []
    report.append("=" * 80)
    report.append("设施便利度空间分析总结报告")
    report.append("=" * 80)
    report.append("")

    report.append("1. 腿长对便利度的整体影响:")
    report.append(f"   - 最小腿长({LEG_LENGTHS[0]}m): 平均多样性 {summary_df.iloc[0]['平均多样性']:.2f}")
    report.append(f"   - 最大腿长({LEG_LENGTHS[-1]}m): 平均多样性 {summary_df.iloc[-1]['平均多样性']:.2f}")
    report.append(f"   - 提升幅度: {summary_df.iloc[-1]['平均多样性'] - summary_df.iloc[0]['平均多样性']:.2f}")
    report.append("")

    report.append("2. 各腿长最适合居住的区域:")
    for _, row in summary_df.iterrows():
        report.append(f"   腿长 {row['腿长_米']}m: {row['最适合居住区域']} (多样性: {row['最适合区域平均多样性']:.2f})")
    report.append("")

    report.append("3. 腿长变化影响最大的区域:")
    for region, change in region_change.nlargest(5).items():
        report.append(f"   {region}: 多样性提升 {change:.2f}")
    report.append("")

    report.append("4. 腿长变化影响最小的区域:")
    for region, change in region_change.nsmallest(5).items():
        report.append(f"   {region}: 多样性提升 {change:.2f}")
    report.append("")

    report.append("5. 建议:")
    high_accessibility_threshold = 7
    for _, row in summary_df.iterrows():
        if row['高便利度占比_%'] >= 75:
            report.append(f"   - 腿长 {row['腿长_米']}m 人群: {row['高便利度占比_%']:.1f}% 社区可满足需求，选择范围广")
        elif row['高便利度占比_%'] < 50:
            report.append(f"   - 腿长 {row['腿长_米']}m 人群: 仅 {row['高便利度占比_%']:.1f}% 社区高便利度，需谨慎选择居住区域")

    report.append("")
    report.append("=" * 80)

    # 保存报告
    report_text = "\n".join(report)
    report_file = OUTPUT_DIR / "便利度空间分析_建议报告.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"已保存建议报告: {report_file.name}")

    # 打印报告
    print("\n" + report_text)

    print("\n" + "=" * 80)
    print("[OK] 空间聚类分析完成！")
    print(f"  - 交互式地图: {len(LEG_LENGTHS)} 个 (位于 {MAP_DIR.name} 目录)")
    print(f"  - 汇总统计: {summary_file.name}")
    print(f"  - 区域统计: {region_file.name}")
    print(f"  - 建议报告: {report_file.name}")
    print("=" * 80)


if __name__ == "__main__":
    main()
