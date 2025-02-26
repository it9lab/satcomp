import json
import ast

# csdotファイルを読み込み、辞書型に変換
data_dict = {}
with open('csdot.json', 'r') as file:
    data_str = json.dumps(file.read())

for i in len(data_str):
    if data_str[i] == "\"{":
        data_str = data_str[i+1:]
    
    if data_str[i] == "}\"":
        data_str = data_str[:i]
    
    if data_str[i] == "\\":

# factors部分を抜き出し、辞書型に変換
factors_str = data_dict["factors"]
root, factors = ast.literal_eval(factors_str)
print("factorsの部分:", factors)