import json
import ast

# csdotファイルを読み込み、辞書型に変換
data_dict = {}
with open('csdot', 'r') as file:
    data_str = json.load(file)
#print(data_str)
data_dict = json.loads(data_str)

# factors部分を抜き出し、辞書型に変換
factors_str = data_dict["factors"]
root, factors = ast.literal_eval(factors_str)
#print("factorsの部分:", factors)

# factorsの辞書型をdot言語に変換
node_dict = {}
rule_dict = {}
text_dict = {}
rank_str = "{rank=same; "

for key, value in factors.items():
    if value is None:
        if key[2] == 0:
            node_dict[key[0]] = f'  "{key}";\n'
        else:
            node_dict[key[0]] = f'  "{key}"[label={chr(key[2])}];\n'
            text_dict[key[0]] = chr(key[2])
        rank_str += f'"{key}"; '
    else:
        for v in value:
            node_dict[v] = f'  "{v}";\n'
            if v[2] == 0 or None:
                rule_dict[(v[0],v[1])] = f'  "{key}" -> "{v}";\n'
            else:
                rule_dict[(v[0],v[1])] = f'  "{key}" -> "{v}";\n'
node_dict = dict(sorted(node_dict.items()))
text_dict = dict(sorted(text_dict.items()))

# dot言語に変換
dot_str = "digraph G {\n"
for key, value in node_dict.items():
    dot_str += value

for key, value in rule_dict.items():
    dot_str += value

dot_str += "  " + rank_str + "}\n"
dot_str += "}"

# dot言語をファイルに書き込み
with open('result.dot', 'w') as file:
    file.write(dot_str)

# dotファイルをpngファイルに変換
import os
os.system("dot -Tpng result.dot -o result.png")