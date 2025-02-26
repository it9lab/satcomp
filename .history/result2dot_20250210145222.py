import json
import ast

# csdotファイルを読み込み、辞書型に変換
with open('csdot', 'r') as file:
    data = file.read()

data_dict = json.loads(data)
print("全データ:", data_dict)

# factors部分を抜き出し、辞書型に変換
factors_str = data_dict['factors']
root, factors = ast.literal_eval(factors_str)
print("factorsの部分:", factors)