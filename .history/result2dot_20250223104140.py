import json
import ast

def cs2str(root, cs):
    # 文字列分解に対応する木構造から整数リスト（文字コード）を復元する関数
    res = []
    (i, j, ref) = root

    if j - i == 1:
        res.append(ref)
    else:
        children = cs[root]
        if ref is None:
            # 内部ノードの場合、子ノードが1個の場合と2個の場合を分岐
            if len(children) == 1 and children[0][2] == "RLrule":
                res += cs2str(children[0], cs)
            else:
                res += cs2str(children[0], cs)
                res += cs2str(children[1], cs)
        elif str(ref).startswith("RLrule"):
            # 連帳圧縮ルールの繰り返しの場合
            # (子ノードの区間の長さから繰り返し回数を計算)
            for k in range(int((children[1][1] - children[0][0]) / (children[0][1] - children[0][0]))):
                res += cs2str(children[0], cs)
        else:
            # それ以外の場合
            if isinstance(ref, tuple):
                n = (ref[0], ref[1], None)
                res += cs2str(n, cs)[ref[2]:ref[2]+(j-i)]
            elif (ref, ref + j - i, None) in cs:
                n = (ref, ref + j - i, None)
                res += cs2str(n, cs)
            else:
                n = (ref, ref + j - i, "RLrule")
                res += cs2str(n, cs)
    return res

def main():
    # csdotファイルを読み込み、辞書型に変換
    with open('csdot', 'r') as file:
        data_str = file.read()
    data_dict = json.loads(data_str)

    # factors部分を抜き出し、(root, factors)に変換
    factors_str = data_dict["factors"]
    root, factors = ast.literal_eval(factors_str)

    # cs2strを用いて文字列復元（文字コードのリストとして復元されるので、chr()で文字に変換）
    text_list = cs2str(root, factors)
    text_list = [chr(x) for x in text_list]
    text = "".join(text_list)

    # factors辞書からDOT記述を作成
    dot_str = "digraph G {\n"
    # グラフ方向：上から下へ
    dot_str += "  rankdir = TB;\n"
    
    # factorsの各親ノードについて、ノードとエッジを出力
    for parent, children in factors.items():
        # 親ノードのラベルはtextの該当部分
        node_label = text[parent[0]:parent[1]]
        dot_str += f'  "{parent}" [label="{node_label}"];\n'
        if children is not None:
            # 子ノードがtupleの場合、複数の子に対してエッジを出力
            if isinstance(children, tuple):
                for child in children:
                    dot_str += f'  "{parent}" -> "{child}";\n'
            # ※必要に応じて他の型への対応を追加可能
    dot_str += "}\n"
    
    # DOTファイルとして出力
    with open("tree.dot", "w") as f:
        f.write(dot_str)
    
    print("DOT形式の木構造をtree.dotとして出力しました。")

if __name__ == "__main__":
    main()