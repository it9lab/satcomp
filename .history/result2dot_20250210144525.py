import json
import ast
import networkx as nx
from networkx.drawing.nx_pydot import write_dot
from graphviz import Source

with open('csdot', 'r') as file:
    data = file.read()

data_dict = json.loads(data)
print(data_dict)