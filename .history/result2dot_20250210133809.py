import json
import ast
import matplotlib.pyplot as plt
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout

# JSON文字列をPythonオブジェクトに変換
text = "abracadabra"
json_string = "{\"date\": \"2025-02-06 06:12:00.184268\", \"status\": \"\", \"algo\": \"cs-sat\", \"file_name\": \"\", \"file_len\": 11, \"time_prep\": 0.024350881576538086, \"time_total\": 0.02724289894104004, \"sol_nvars\": 1377, \"sol_nhard\": 7749, \"sol_nsoft\": 121, \"sol_navgclause\": 2.4805781391147246, \"sol_ntotalvars\": 19222, \"sol_nmaxclause\": 20, \"factor_size\": 12, \"factors\": \"((0, 11, None), {(7, 11, 0): None, (6, 7, 100): None, (5, 6, 97): None, (4, 5, 99): None, (3, 4, 97): None, (2, 3, 114): None, (1, 2, 98): None, (0, 1, 97): None, (0, 4, None): ((0, 3, None), (3, 4, 97)), (0, 11, None): ((0, 7, None), (7, 11, 0)), (0, 5, None): ((0, 4, None), (4, 5, 99)), (0, 6, None): ((0, 5, None), (5, 6, 97)), (0, 7, None): ((0, 6, None), (6, 7, 100)), (0, 2, None): ((0, 1, 97), (1, 2, 98)), (0, 3, None): ((0, 2, None), (2, 3, 114))})\"}"
data = json.loads(json_string)

# factors部分をパース
factors_str = data['factors']
root, factors = ast.literal_eval(factors_str)

# 木構造を生成
G = nx.DiGraph()

def add_edges(factor):
    if isinstance(factor, tuple) and len(factor) == 3:
        start, end, _ = factor
        label = text[start:end]
        G.add_node(factor, label=label)
        if factor in factors:
            children = factors[factor]
            if isinstance(children, tuple):
                for child in children:
                    G.add_edge(factor, child)
                    add_edges(child)

add_edges(root)

# ノードラベルを取得
labels = nx.get_node_attributes(G, 'label')

# 木構造の図を生成
pos = graphviz_layout(G, prog='dot')
nx.draw(G, pos, labels=labels, with_labels=True, node_size=1000, node_color="skyblue", font_size=10, font_weight="bold", arrows=True)
plt.show()