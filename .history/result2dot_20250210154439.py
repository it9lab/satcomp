import json
import ast

# csdotファイルを読み込み、辞書型に変換
with open('csdot', 'r') as file:
    data_dict = json.load(file)

# factors部分を抜き出し、辞書型に変換
factors_str = data_dict['factors"]
root, factors = ast.literal_eval(factors_str)
print("factorsの部分:", factors)