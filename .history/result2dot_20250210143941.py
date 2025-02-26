import json
import ast
import networkx as nx
from networkx.drawing.nx_pydot import write_dot
from graphviz import Source

# JSON文字列をPythonオブジェクトに変換
text = "abracadabra"