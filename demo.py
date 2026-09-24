"""Synthetic local demo of the original server; no real POI or API key needed."""
import argparse
import math

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import KDTree

import app as original

NOTICE = '合成数据演示：社区、设施与路网均为虚构，不代表福州真实结果。原服务器的腿长参数仅影响显示，零权重不代表排除类别。'


def load_synthetic_data():
    """Construct a deterministic 7x7 artificial network near a map reference point."""
    graph = nx.Graph()
    step = 250.0
    for row in range(7):
        for col in range(7):
            graph.add_node(row * 7 + col, x=119.28 + col * step / (111000 * math.cos(math.radians(26.07))),
                           y=26.07 + row * step / 111000)
            if row:
                graph.add_edge((row - 1) * 7 + col, row * 7 + col, length=step)
            if col:
                graph.add_edge(row * 7 + col - 1, row * 7 + col, length=step)
    communities = []
    for i, node in enumerate([0, 8, 16, 24, 32, 48], 1):
        communities.append(dict(name=f'虚构社区{i}', region='合成示例区', lat=graph.nodes[node]['y'], lng=graph.nodes[node]['x']))
    facilities = []
    for i, config in enumerate(original.FACILITY_CATEGORIES.values()):
        for j in range(4):
            node = (i * 5 + j * 9) % 49
            facilities.append(dict(name=f'虚构设施{i+1}-{j+1}', category=config['data_name'], node=node,
                                   lat=graph.nodes[node]['y'], lng=graph.nodes[node]['x']))
    original.G = graph
    original.community_df = pd.DataFrame(communities)
    original.facility_df = pd.DataFrame(facilities)
    original.node_coords = np.array([[graph.nodes[n]['y'], graph.nodes[n]['x']] for n in graph])
    original.kdtree = KDTree(original.node_coords)


def create_demo_app():
    load_synthetic_data()
    application = original.app
    if not application.config.get('SYNTHETIC_DEMO'):
        application.config['SYNTHETIC_DEMO'] = True

        @application.after_request
        def mark_synthetic(response):
            if response.mimetype == 'text/html':
                banner = '<div style="padding:14px;background:#fff3cd;color:#664d03;position:relative;z-index:99999">'+NOTICE+'</div>'
                response.set_data(response.get_data(as_text=True).replace('<body>', '<body>'+banner, 1))
            elif response.is_json:
                payload = response.get_json()
                if isinstance(payload, dict):
                    payload['synthetic_demo'] = True
                    payload['notice'] = NOTICE
                    response.set_data(application.json.dumps(payload))
            return response
    return application


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    print(NOTICE)
    create_demo_app().run(host='127.0.0.1', port=args.port, debug=False)
