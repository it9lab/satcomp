import json
import ast

# csdotファイルを読み込み、辞書型に変換
data_dict = {}
with open('csdot', 'r') as file:
    data_str = json.load(file)
print(data_str)
data_dict = json.loads(data_str)

# factors部分を抜き出し、辞書型に変換
factors_str = data_dict["factors"]
root, factors = ast.literal_eval(factors_str)
print("factorsの部分:", factors)

# factorsの辞書型をdot言語に変換
node_dict = {}
text_dict = {}
rule_dict = {}  # Initialize rule_dict

for key, value in factors.items():
    if value is None:
        if key[2] == 0:
            node_dict[key[0]] = f'  "{key}";\n'
        else:
            node_dict[key[0]] = f'  "{key}"[label={chr(key[2])}];\n'
            text_dict[key[0]] = chr(key[2])
    else:
        for v in value:
            

text_str = ""
for i in dict(sorted(text_dict.items())).keys():
    text_str += text_dict[i]

# dot言語をファイルに書き込み
with open('result.dot', 'w') as file:
    file.write(dot_str)

# dotファイルをpngファイルに変換
import os
os.system("dot -Tpng result.dot -o result.png")