"""
交互式便利度地图 - Flask服务器
用户可以自定义腿长和设施权重，实时计算专属地图
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
import json

app = Flask(__name__)

# =========================================================
# 全局变量（预加载数据）
# =========================================================

DATA_DIR = Path(__file__).parent
CACHE_DIR = DATA_DIR / "输出"
G = None  # 路网图
community_df = None  # 社区数据
facility_df = None  # 设施数据
node_coords = None  # 节点坐标
kdtree = None  # KD树

# 设施类别配置（与实际POI数据中的类别名称一致）
FACILITY_CATEGORIES = {
    '餐饮': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '餐饮设施'},
    '超市': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '超市商场'},
    '医疗': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '医疗设施'},
    '教育': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '教育设施'},
    '交通': {'default_weight': 1.0, 'default_radius': 1000, 'data_name': '交通设施'},
    '休闲': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '休闲娱乐设施'},
    '公园': {'default_weight': 1.0, 'default_radius': 1500, 'data_name': '公园广场'},
    '金融': {'default_weight': 1.0, 'default_radius': 800, 'data_name': '金融设施'},
}


# =========================================================
# 数据加载函数
# =========================================================

def load_data():
    """预加载所有数据"""
    global G, community_df, facility_df, node_coords, kdtree
    
    print("正在加载数据...")
    
    # 1. 加载路网图
    graph_cache = CACHE_DIR / "缓存_路网图.gpickle"
    if graph_cache.exists():
        print("  [1/4] 从缓存加载路网图...")
        with open(graph_cache, 'rb') as f:
            G = pickle.load(f)
        print(f"        路网: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
    else:
        print("  ✗ 路网缓存文件不存在，请先运行主分析脚本生成缓存")
        return False
    
    # 2. 加载社区数据
    community_cache = CACHE_DIR / "缓存_总社区poi.xlsx"
    if community_cache.exists():
        print("  [2/4] 从缓存加载社区数据...")
        community_df = pd.read_excel(community_cache)
        print(f"        社区: {len(community_df)} 个")
    else:
        print("  ✗ 社区缓存文件不存在")
        return False
    
    # 3. 加载设施数据
    facility_cache = CACHE_DIR / "缓存_总设施poi.xlsx"
    facility_cache_with_nodes = CACHE_DIR / "缓存_总设施poi_带节点.xlsx"
    
    if facility_cache_with_nodes.exists():
        print("  [3/4] 从缓存加载设施数据（已包含节点）...")
        facility_df = pd.read_excel(facility_cache_with_nodes)
        print(f"        设施: {len(facility_df)} 个（节点已预分配）")
    elif facility_cache.exists():
        print("  [3/4] 从缓存加载设施数据...")
        facility_df = pd.read_excel(facility_cache)
        print(f"        设施: {len(facility_df)} 个")
        
        # 需要为设施分配节点
        print("  [4/4] 构建索引并分配节点（首次需要几分钟）...")
        node_coords = np.array([[G.nodes[n]['y'], G.nodes[n]['x']] for n in G.nodes()])
        kdtree = KDTree(node_coords)
        
        print("  为设施分配路网节点...")
        facility_nodes = []
        distances = []
        for idx, row in facility_df.iterrows():
            if (idx + 1) % 1000 == 0:
                print(f"    进度: {idx + 1}/{len(facility_df)}")
            node, dist = find_nearest_node(row['lat'], row['lng'], return_distance=True)
            facility_nodes.append(node)
            distances.append(dist)
        facility_df['node'] = facility_nodes
        
        # 显示距离统计
        distances = np.array(distances)
        print(f"\n  📊 设施到路网节点的距离统计：")
        print(f"    最小距离: {distances.min():.2f} 米")
        print(f"    最大距离: {distances.max():.2f} 米")
        print(f"    平均距离: {distances.mean():.2f} 米")
        print(f"    中位数: {np.median(distances):.2f} 米")
        print(f"    超过500米: {(distances > 500).sum()} 个 ({(distances > 500).sum()/len(distances)*100:.1f}%)")
        print(f"    超过1000米: {(distances > 1000).sum()} 个 ({(distances > 1000).sum()/len(distances)*100:.1f}%)")
        
        # 保存带节点的设施数据
        print(f"  保存节点数据到: {facility_cache_with_nodes.name}")
        facility_df.to_excel(facility_cache_with_nodes, index=False)
        print("  ✓ 节点数据已保存，下次启动将直接加载")
    else:
        print("  ✗ 设施缓存文件不存在")
        return False
    
    # 4. 构建KD树用于快速查找（如果还没构建）
    if kdtree is None:
        print("  [4/4] 构建KD树索引...")
        node_coords = np.array([[G.nodes[n]['y'], G.nodes[n]['x']] for n in G.nodes()])
        kdtree = KDTree(node_coords)
    
    print("✓ 数据加载完成\n")
    return True


# =========================================================
# 计算函数
# =========================================================

def calculate_walking_distance(leg_length):
    """
    根据腿长计算15分钟步行距离
    
    Args:
        leg_length: 腿长（米）
    
    Returns:
        15分钟步行距离（米）
    """
    g = 9.8  # 重力加速度
    FS = np.sqrt(leg_length * g)  # 弗劳德速度
    TPWS = 0.42 * FS  # 首选步行速度（米/秒）
    distance_15min = TPWS * 15 * 60  # 15分钟步行距离
    return distance_15min


def find_nearest_node(lat, lng, return_distance=False):
    """
    查找最近的路网节点
    
    Args:
        lat: 纬度
        lng: 经度
        return_distance: 是否返回距离（度数单位）
    
    Returns:
        如果return_distance=False，返回节点ID
        如果return_distance=True，返回(节点ID, 距离)
    """
    dist, idx = kdtree.query([lat, lng])
    node_id = list(G.nodes())[idx]
    
    if return_distance:
        # 转换为米（粗略估算：1度≈111km）
        dist_meters = dist * 111000
        return node_id, dist_meters
    return node_id


def calculate_accessibility(community_row, leg_length, weights, radii):
    """
    计算单个社区的便利度（优化版：使用节点查找而非遍历设施）
    
    Args:
        community_row: 社区数据行
        leg_length: 腿长（米）
        weights: 各设施类别权重字典
        radii: 各设施类别搜索半径字典
    
    Returns:
        便利度指标字典
    """
    # 找到社区最近的路网节点
    comm_node = find_nearest_node(community_row['lat'], community_row['lng'])
    
    # ✅ 关键：权重影响搜索距离 - 权重越大→距离越近→搜索半径 = 基础半径 / 权重
    adjusted_radii = {cat: radii[cat] / max(weights[cat], 0.1) for cat in FACILITY_CATEGORIES.keys()}
    
    # 计算从该节点到所有节点的最短距离（使用最大搜索半径限制）
    max_radius = max(adjusted_radii.values())
    try:
        distances = nx.single_source_dijkstra_path_length(G, comm_node, cutoff=max_radius, weight='length')
    except:
        # 如果节点不在图中，返回零值
        distances = {}
    
    # ✅ 关键优化：直接检查可达节点，而不是遍历所有设施
    category_counts = {}
    category_scores = {}
    
    for category in FACILITY_CATEGORIES.keys():
        # 筛选该类设施（使用数据中的实际类别名）
        data_category_name = FACILITY_CATEGORIES[category]['data_name']
        category_facilities = facility_df[facility_df['category'] == data_category_name]
        
        # ✅ 优化：直接用节点列表判断，不遍历DataFrame行（使用调整后的半径）
        adjusted_radius = adjusted_radii[category]
        count = sum(1 for node in category_facilities['node'].values 
                   if node in distances and distances[node] <= adjusted_radius)
        
        category_counts[category] = count
    
    # 计算多样性（有设施的类别数）- 与弗劳德数脚本一致
    diversity = sum(1 for count in category_counts.values() if count > 0)
    
    # 计算综合便利度 - 与弗劳德数脚本一致：多样性 × 100 + log10(总设施数+1) × 10
    total_facilities = sum(category_counts.values())
    if total_facilities > 0:
        quantity_score = np.log10(total_facilities + 1) * 10
    else:
        quantity_score = 0
    comprehensive_score = diversity * 100 + quantity_score
    
    # 返回原始数据（总便利度需要在所有社区计算后归一化）
    return {
        '多样性': diversity,
        '综合便利度': comprehensive_score,
        '总设施数': total_facilities,
        **{f'{cat}_便利度': category_counts[cat] for cat in FACILITY_CATEGORIES.keys()}
    }


def create_custom_map(leg_length, weights, radii):
    """
    创建自定义便利度地图
    
    Args:
        leg_length: 腿长（米）
        weights: 各设施类别权重字典
        radii: 各设施类别搜索半径字典
    
    Returns:
        地图HTML字符串
    """
    print(f"开始计算地图 (腿长={leg_length}m)...")
    import sys
    sys.stdout.flush()
    
    # 第一遍：计算所有社区的原始数据
    raw_results = []
    total = len(community_df)
    print(f"  [第1遍] 总共需要计算 {total} 个社区...")
    print(f"  预计需要时间: {total * 2 // 60} 分钟（每个社区约2秒）")
    sys.stdout.flush()
    
    import time
    start_time = time.time()
    
    for idx, row in community_df.iterrows():
        if (idx + 1) % 10 == 0:  # 每10个显示一次进度
            elapsed = time.time() - start_time
            speed = (idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - idx - 1) / speed if speed > 0 else 0
            print(f"  进度: {idx + 1}/{total} ({(idx+1)/total*100:.1f}%) | "
                  f"已用时: {elapsed/60:.1f}分钟 | 预计剩余: {remaining/60:.1f}分钟")
            import sys
            sys.stdout.flush()  # 强制刷新输出缓冲区
        
        result = calculate_accessibility(row, leg_length, weights, radii)
        raw_results.append({
            '社区名称': row['name'],
            '区域': row.get('region', '未知'),
            '纬度': row['lat'],
            '经度': row['lng'],
            **result
        })
    
    total_time = time.time() - start_time
    print(f"  ✓ 第一遍计算完成！总用时: {total_time/60:.1f}分钟")
    import sys
    sys.stdout.flush()
    
    # 第二遍：计算每类设施的最大值（用于归一化）
    print(f"  [第2遍] 计算归一化参数...")
    sys.stdout.flush()
    df_temp = pd.DataFrame(raw_results)
    max_values = {}
    for cat in FACILITY_CATEGORIES.keys():
        col_name = f'{cat}_便利度'
        max_val = df_temp[col_name].max()
        max_values[cat] = max_val if max_val > 0 else 1
    
    # 第三遍：计算总便利度（归一化后求和）- 与弗劳德数脚本一致
    print(f"  [第3遍] 计算总便利度...")
    import sys
    sys.stdout.flush()
    results = []
    for rec in raw_results:
        normalized_scores = []
        for cat in FACILITY_CATEGORIES.keys():
            col_name = f'{cat}_便利度'
            normalized = rec[col_name] / max_values[cat]
            normalized_scores.append(normalized)
        
        rec['总便利度'] = sum(normalized_scores)
        results.append(rec)
    
    df = pd.DataFrame(results)
    print(f"  ✓ 所有计算完成！")
    sys.stdout.flush()
    
    # 调试：检查DataFrame
    print(f"\n生成的DataFrame:")
    print(f"  行数: {len(df)}")
    print(f"  列名: {df.columns.tolist()}")
    print(f"  前3行:\n{df.head(3)}")
    
    # 分级（基于多样性）
    df['等级'] = pd.cut(df['多样性'], 
                        bins=[-0.1, 4, 6, 8.1],
                        labels=['低多样性(≤4类)', '中等多样性(5-6类)', '高多样性(7-8类)'])
    
    print("生成地图...")
    import sys
    sys.stdout.flush()
    
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
    <style>
        .info-panel {{
            position: fixed;
            top: 10px;
            left: 50px;
            width: 350px;
            background-color: white;
            border: 2px solid #667eea;
            border-radius: 8px;
            z-index: 9999;
            font-size: 13px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .info-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 15px;
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .info-header:hover {{
            background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
        }}
        .info-content {{
            padding: 12px 15px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .info-content.collapsed {{
            display: none;
        }}
        .toggle-icon {{
            font-size: 18px;
            transition: transform 0.3s;
        }}
        .toggle-icon.collapsed {{
            transform: rotate(-90deg);
        }}
        .stat-item {{
            margin: 6px 0;
            padding: 4px 0;
        }}
    </style>
    <div class="info-panel">
        <div class="info-header" onclick="toggleInfo()">
            <span><b>🎯 MapYou 个性化便利度分析</b></span>
            <span class="toggle-icon" id="toggle-icon">▼</span>
        </div>
        <div class="info-content" id="info-content">
            <div style="background: #f0f4ff; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
                <b>参数设置：</b><br>
                腿长 {leg_length} 米 | 15分钟步行距离: {walking_distance:.0f} 米<br>
                <b>权重：</b> {weights_str}
            </div>
            <div style="background: #fff4e6; padding: 8px; border-radius: 4px; margin-bottom: 8px; font-size: 12px;">
                💡 <b>权重机制：</b>搜索半径 = 基础半径 / 权重<br>
                权重越大 → 要求越近
            </div>
            <b>三大指标统计：</b>
            <div class="stat-item">📊 平均多样性: <b>{df['多样性'].mean():.2f}/8.00</b><br>
                <small style="color: #666;">有设施的类别数</small>
            </div>
            <div class="stat-item">📊 平均综合便利度: <b>{df['综合便利度'].mean():.2f}</b><br>
                <small style="color: #666;">多样性×100 + log10×10</small>
            </div>
            <div class="stat-item">📊 平均总便利度: <b>{df['总便利度'].mean():.2f}/8.00</b><br>
                <small style="color: #666;">归一化后求和</small>
            </div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #e0e0e0;">
            <div style="background: #e8f5e9; padding: 6px; border-radius: 4px;">
                ✅ 完全覆盖(8类): <b>{(df['多样性']==8).sum()} 个社区</b>
            </div>
            <div style="margin-top: 8px; font-size: 11px; color: #666; text-align: center;">
                点击社区标记查看详情 | 使用图层控制切换视图
            </div>
        </div>
    </div>
    <script>
        function toggleInfo() {{
            const content = document.getElementById('info-content');
            const icon = document.getElementById('toggle-icon');
            content.classList.toggle('collapsed');
            icon.classList.toggle('collapsed');
        }}
    </script>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # 添加社区标记
    for level, color in [('高多样性(7-8类)', 'green'), ('中等多样性(5-6类)', 'orange'), ('低多样性(≤4类)', 'red')]:
        df_level = df[df['等级'] == level]
        marker_cluster = MarkerCluster(name=level).add_to(m)
        
        for idx, row in df_level.iterrows():
            popup_html = f"""
            <div style="font-family: Arial; font-size: 12px; width: 280px;">
                <b>{row['社区名称']}</b><br>
                区域: {row['区域']}<br>
                <hr style="margin: 5px 0;">
                <b>三大便利度指标：</b><br>
                📊 多样性: {row['多样性']:.0f}/8 (有设施的类别数)<br>
                📊 综合便利度: {row['综合便利度']:.2f}<br>
                📊 总便利度: {row['总便利度']:.2f}/8.00<br>
                总设施数: {row['总设施数']:.0f}个<br>
                <hr style="margin: 5px 0;">
                <b>各类设施数量：</b><br>
            """
            
            for cat in FACILITY_CATEGORIES.keys():
                count = row[f'{cat}_便利度']
                weight = weights[cat]
                base_r = radii[cat]
                actual_r = base_r / max(weight, 0.1)
                popup_html += f"{cat} (权重{weight:.1f}, 搜索{actual_r:.0f}m): {count:.0f}个<br>"
            
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
    
    # 添加三个热力图图层 - 与弗劳德数脚本一致
    # 1. 多样性热力图（0-8）
    diversity_group = folium.FeatureGroup(name='📊 多样性热力图 (0-8)', show=True)
    diversity_data = [[row['纬度'], row['经度'], row['多样性']] for idx, row in df.iterrows()]
    HeatMap(diversity_data,
            min_opacity=0.3,
            max_val=8.0,
            radius=15, 
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(diversity_group)
    diversity_group.add_to(m)
    
    # 2. 综合便利度热力图
    comprehensive_group = folium.FeatureGroup(name='📊 综合便利度热力图', show=False)
    comprehensive_data = [[row['纬度'], row['经度'], row['综合便利度']] for idx, row in df.iterrows()]
    comp_max = df['综合便利度'].max()
    HeatMap(comprehensive_data,
            min_opacity=0.3,
            max_val=comp_max,
            radius=15, 
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(comprehensive_group)
    comprehensive_group.add_to(m)
    
    # 3. 总便利度热力图（0-8）
    total_group = folium.FeatureGroup(name='📊 总便利度热力图 (0-8)', show=False)
    total_data = [[row['纬度'], row['经度'], row['总便利度']] for idx, row in df.iterrows()]
    HeatMap(total_data,
            min_opacity=0.3,
            max_val=8.0,
            radius=15, 
            blur=20,
            gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(total_group)
    total_group.add_to(m)
    
    # 图层控制
    folium.LayerControl(collapsed=False).add_to(m)
    
    print("✓ 地图生成完成")
    
    # 返回HTML
    return m._repr_html_()


# =========================================================
# Flask路由
# =========================================================

@app.route('/')
def index():
    """主页"""
    return render_template('interactive_map.html', 
                          categories=FACILITY_CATEGORIES)


@app.route('/calculate', methods=['POST'])
def calculate():
    """计算便利度地图"""
    import sys
    print("\n" + "="*60)
    print("收到计算请求")
    print("="*60)
    sys.stdout.flush()  # 立即显示
    
    try:
        data = request.json
        print(f"请求数据: {data}")
        
        # 获取参数
        leg_length = float(data.get('leg_length', 0.85))
        print(f"腿长: {leg_length}m")
        
        # 获取权重
        weights = {}
        for cat in FACILITY_CATEGORIES.keys():
            weights[cat] = float(data.get(f'weight_{cat}', 1.0))
        print(f"权重: {weights}")
        
        # 获取搜索半径（可选，使用默认值或自定义）
        radii = {}
        for cat in FACILITY_CATEGORIES.keys():
            default_radius = FACILITY_CATEGORIES[cat]['default_radius']
            radii[cat] = float(data.get(f'radius_{cat}', default_radius))
        print(f"搜索半径: {radii}")
        import sys
        sys.stdout.flush()
        
        # 生成地图
        print("\n开始生成地图...")
        sys.stdout.flush()
        map_html = create_custom_map(leg_length, weights, radii)
        print("✓ 地图生成成功\n")
        
        return jsonify({
            'success': True,
            'map_html': map_html
        })
        
    except Exception as e:
        import traceback
        print(f"\n✗ 错误: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'data_loaded': G is not None and community_df is not None
    })


# =========================================================
# 主程序
# =========================================================

if __name__ == '__main__':
    try:
        print("=" * 80)
        print("MapYou - 福州市社区便利度个性化分析")
        print("=" * 80)
        print(f"\n当前工作目录: {Path.cwd()}")
        print(f"程序文件位置: {Path(__file__).parent}")
        print(f"缓存目录: {CACHE_DIR}")
        print(f"缓存目录是否存在: {CACHE_DIR.exists()}")
        
        # 加载数据
        if load_data():
            print("\n服务器准备就绪！")
            print("浏览器将自动打开，如未打开请手动访问: http://127.0.0.1:5000")
            print("=" * 80)
            print("\n按 Ctrl+C 停止服务器")
            print()
            
            # 自动打开浏览器
            import webbrowser
            import threading
            import time
            def open_browser():
                time.sleep(2)
                webbrowser.open('http://127.0.0.1:5000')
            threading.Thread(target=open_browser, daemon=True).start()
            
            # 启动服务器
            app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
        else:
            print("\n✗ 数据加载失败！")
            print("\n可能的原因：")
            print("1. 缓存文件不存在或路径不正确")
            print("2. 数据文件损坏")
            print(f"\n请检查以下文件是否存在：")
            print(f"  - {CACHE_DIR / '缓存_路网图.gpickle'}")
            print(f"  - {CACHE_DIR / '缓存_总社区poi.xlsx'}")
            print(f"  - {CACHE_DIR / '缓存_总设施poi.xlsx'}")
            input("\n按回车键退出...")
    except Exception as e:
        print("\n" + "=" * 80)
        print("程序运行出错！")
        print("=" * 80)
        import traceback
        print("\n错误详情:")
        print(traceback.format_exc())
        print("\n" + "=" * 80)
        input("\n按回车键退出...")
