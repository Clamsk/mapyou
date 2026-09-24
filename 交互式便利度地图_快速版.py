"""
交互式便利度地图 - 快速演示版
只计算每个区域的前20个社区，快速生成结果
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import networkx as nx
from scipy.spatial import KDTree
import folium
from folium.plugins import MarkerCluster, HeatMap

app = Flask(__name__)

# 全局变量
DATA_DIR = Path(__file__).parent
CACHE_DIR = DATA_DIR / "输出"
G = None
community_df = None
facility_df = None
node_coords = None
kdtree = None

# 设施类别配置
FACILITY_CATEGORIES = {
    '餐饮': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '餐饮设施'},
    '超市': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '商业超市'},
    '医疗': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '医疗设施'},
    '教育': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '教育设施'},
    '交通': {'default_weight': 1.0, 'default_radius': 1000, 'data_name': '交通设施'},
    '体育': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '体育设施'},
    '公园': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '公园广场'},
    '便民': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '便民服务设施'},
}

# 演示模式：每个区域只计算前N个社区
DEMO_SAMPLES_PER_REGION = 20


def load_data():
    """预加载所有数据"""
    global G, community_df, facility_df, node_coords, kdtree

    print("正在加载数据...")

    # 加载路网图
    graph_cache = CACHE_DIR / "缓存_路网图.gpickle"
    if graph_cache.exists():
        print("  [1/3] 从缓存加载路网图...")
        with open(graph_cache, 'rb') as f:
            G = pickle.load(f)
        print(f"        路网: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
    else:
        print("  ✗ 路网缓存文件不存在")
        return False

    # 加载社区数据
    community_cache = CACHE_DIR / "缓存_总社区poi.xlsx"
    if community_cache.exists():
        print("  [2/3] 从缓存加载社区数据...")
        community_df = pd.read_excel(community_cache)
        print(f"        社区: {len(community_df)} 个")

        # 演示模式：每个区域取样
        sampled_communities = []
        for region in community_df['region'].unique():
            region_data = community_df[community_df['region'] == region].head(DEMO_SAMPLES_PER_REGION)
            sampled_communities.append(region_data)
        community_df = pd.concat(sampled_communities, ignore_index=True)
        print(f"        演示模式：采样后 {len(community_df)} 个社区")
    else:
        print("  ✗ 社区缓存文件不存在")
        return False

    # 加载设施数据
    facility_cache = CACHE_DIR / "缓存_总设施poi.xlsx"
    if facility_cache.exists():
        print("  [3/3] 从缓存加载设施数据...")
        facility_df = pd.read_excel(facility_cache)
        print(f"        设施: {len(facility_df)} 个")
    else:
        print("  ✗ 设施缓存文件不存在")
        return False

    # 构建KD树
    print("  构建KD树索引...")
    node_coords = np.array([[G.nodes[n]['y'], G.nodes[n]['x']] for n in G.nodes()])
    kdtree = KDTree(node_coords)

    print("✓ 数据加载完成\n")
    return True


def calculate_walking_distance(leg_length):
    """根据腿长计算15分钟步行距离"""
    g = 9.8
    FS = np.sqrt(leg_length * g)
    TPWS = 0.42 * FS
    distance_15min = TPWS * 15 * 60
    return distance_15min


def find_nearest_node(lat, lng):
    """查找最近的路网节点"""
    dist, idx = kdtree.query([lat, lng])
    node_id = list(G.nodes())[idx]
    return node_id


def calculate_accessibility(community_row, leg_length, weights, radii):
    """计算单个社区的便利度"""
    comm_node = find_nearest_node(community_row['lat'], community_row['lng'])

    max_radius = max(radii.values())
    try:
        distances = nx.single_source_dijkstra_path_length(G, comm_node, cutoff=max_radius, weight='length')
    except:
        distances = {}

    accessible_nodes = set(distances.keys())
    category_counts = {}
    category_scores = {}

    for category in FACILITY_CATEGORIES.keys():
        data_category_name = FACILITY_CATEGORIES[category]['data_name']
        category_facilities = facility_df[facility_df['category'] == data_category_name]

        count = 0
        for _, fac in category_facilities.iterrows():
            fac_node = find_nearest_node(fac['lat'], fac['lng'])
            if fac_node in accessible_nodes and distances.get(fac_node, float('inf')) <= radii[category]:
                count += 1

        category_counts[category] = count
        category_scores[category] = 1 if count > 0 else 0

    diversity = sum(category_scores.values())
    weighted_scores = {cat: category_scores[cat] * weights[cat] for cat in FACILITY_CATEGORIES.keys()}
    total_weight = sum(weights.values())
    weighted_accessibility = sum(weighted_scores.values()) / total_weight * 8
    total_facilities = sum(category_counts.values())
    comprehensive_score = diversity * 100 + np.log10(total_facilities + 1) * 10

    return {
        '多样性': diversity,
        '加权便利度': weighted_accessibility,
        '综合便利度': comprehensive_score,
        '总设施数': total_facilities,
        **{f'{cat}_数量': category_counts[cat] for cat in FACILITY_CATEGORIES.keys()},
        **{f'{cat}_便利度': category_scores[cat] for cat in FACILITY_CATEGORIES.keys()}
    }


def create_custom_map(leg_length, weights, radii):
    """创建自定义便利度地图"""
    print(f"开始计算地图 (腿长={leg_length}m, 演示模式)...")

    import time
    start_time = time.time()

    results = []
    total = len(community_df)
    for idx, row in community_df.iterrows():
        if (idx + 1) % 10 == 0:
            elapsed = time.time() - start_time
            speed = (idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - idx - 1) / speed if speed > 0 else 0
            print(f"  进度: {idx + 1}/{total} ({(idx+1)/total*100:.1f}%) | 剩余: {remaining:.0f}秒")

        result = calculate_accessibility(row, leg_length, weights, radii)
        results.append({
            '社区名称': row['name'],
            '区域': row.get('region', '未知'),
            '纬度': row['lat'],
            '经度': row['lng'],
            **result
        })

    total_time = time.time() - start_time
    print(f"  ✓ 计算完成！用时: {total_time:.1f}秒")

    df = pd.DataFrame(results)
    df['等级'] = pd.cut(df['加权便利度'],
                        bins=[-0.1, 4, 7, 8.1],
                        labels=['低便利度', '中等便利度', '高便利度'])

    print("生成地图HTML...")

    # 创建地图
    center_lat = df['纬度'].mean()
    center_lon = df['经度'].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )

    # 添加标题
    walking_distance = calculate_walking_distance(leg_length)
    weights_str = ', '.join([f'{cat}: {w:.1f}' for cat, w in weights.items()])

    title_html = f'''
    <div style="position: fixed;
                top: 10px; left: 50px; width: 700px; height: 220px;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:14px; padding: 10px">
        <b style="font-size:16px">🎯 个性化设施便利度地图 (演示版)</b><br>
        <b style="color: #ff6b6b;">⚠️ 演示模式：仅计算了 {len(df)} 个采样社区（每区域{DEMO_SAMPLES_PER_REGION}个）</b><br>
        <b>参数设置：</b> 腿长 {leg_length} 米 | 15分钟步行距离: {walking_distance:.0f} 米<br>
        <b>设施权重：</b> {weights_str}<br>
        <hr style="margin: 5px 0;">
        <b>统计结果：</b><br>
        平均多样性: {df['多样性'].mean():.2f} | 平均加权便利度: {df['加权便利度'].mean():.2f}/8.00<br>
        <span style="color:green">●</span> 高便利度: {(df['加权便利度']>=7).sum()} 个
        <span style="color:orange">●</span> 中等: {((df['加权便利度']>=4)&(df['加权便利度']<7)).sum()} 个
        <span style="color:red">●</span> 低: {(df['加权便利度']<4).sum()} 个<br>
        <hr style="margin: 5px 0;">
        <small>点击社区标记查看详细信息 | 计算用时: {total_time:.1f}秒</small>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

    # 添加社区标记
    for level, color in [('高便利度', 'green'), ('中等便利度', 'orange'), ('低便利度', 'red')]:
        df_level = df[df['等级'] == level]
        marker_cluster = MarkerCluster(name=level).add_to(m)

        for idx, row in df_level.iterrows():
            popup_html = f"""
            <div style="font-family: Arial; font-size: 12px; width: 250px;">
                <b>{row['社区名称']}</b><br>
                区域: {row['区域']}<br>
                <hr style="margin: 5px 0;">
                <b>便利度指标：</b><br>
                多样性: {row['多样性']:.0f}/8<br>
                加权便利度: {row['加权便利度']:.2f}/8.00<br>
                综合便利度: {row['综合便利度']:.2f}<br>
                总设施数: {row['总设施数']:.0f}<br>
                <hr style="margin: 5px 0;">
                <b>各类设施数量：</b><br>
            """

            for cat in FACILITY_CATEGORIES.keys():
                count = row[f'{cat}_数量']
                weight = weights[cat]
                popup_html += f"{cat} (权重{weight:.1f}): {count:.0f}个<br>"

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

    # 添加热力图
    heat_data = [[row['纬度'], row['经度'], row['加权便利度']] for idx, row in df.iterrows()]
    HeatMap(heat_data, name='加权便利度热力图',
            min_opacity=0.3,
            max_val=8.0,
            radius=15,
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    print("✓ 地图生成完成")
    return m._repr_html_()


@app.route('/')
def index():
    """主页"""
    return render_template('interactive_map.html',
                          categories=FACILITY_CATEGORIES)


@app.route('/calculate', methods=['POST'])
def calculate():
    """计算便利度地图"""
    print("\n" + "="*60)
    print("收到计算请求（演示模式）")
    print("="*60)

    try:
        data = request.json
        leg_length = float(data.get('leg_length', 0.85))

        weights = {}
        for cat in FACILITY_CATEGORIES.keys():
            weights[cat] = float(data.get(f'weight_{cat}', 1.0))

        radii = {}
        for cat in FACILITY_CATEGORIES.keys():
            default_radius = FACILITY_CATEGORIES[cat]['default_radius']
            radii[cat] = float(data.get(f'radius_{cat}', default_radius))

        map_html = create_custom_map(leg_length, weights, radii)

        return jsonify({
            'success': True,
            'map_html': map_html
        })

    except Exception as e:
        import traceback
        print(f"\n✗ 错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    print("=" * 80)
    print("交互式便利度地图服务器 - 快速演示版")
    print("=" * 80)

    if load_data():
        print("\n服务器准备就绪！")
        print("请在浏览器中打开: http://127.0.0.1:5001")
        print("=" * 80)
        print("\n")

        app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
    else:
        print("\n✗ 数据加载失败")
