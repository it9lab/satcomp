import json
import ast

def cs2dot(root, cs):


def main():
    # csdotファイルを読み込み、辞書型に変換
    data_dict = {}
    with open('csdot', 'r') as file:
        data_str = json.load(file)
    #print(data_str)
    data_dict = json.loads(data_str)

    # factors部分を抜き出し、辞書型に変換
    factors_str = data_dict["factors"]
    root, factors = ast.literal_eval(factors_str)
    print("factorsの部分:", factors)
    
    # factors部分をdotファイルに変換

    # dotファイルをpngファイルに変換
    import os
    os.system("dot -Tpng result.dot -o result.png")