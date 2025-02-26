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
dot_str = "digraph G {\n"
rank_str = "{rank=same;"
for key, value in factors.items():
    if value == None:
        dot_str += f'  "{chr(key)}"\n'
        rank_str += f' "{key}";'
    else:
        for v in value:
            dot_str += f'  "{key}" -> "{v}"\n'
dot_str += rank_str + "}\n"
dot_str += "}"
print(dot_str)

# dot言語をファイルに書き込み
with open('result.dot', 'w') as file:
    file.write(dot_str)

# dotファイルをpngファイルに変換
import os
os.system("dot -Tpng result.dot -o result.png")