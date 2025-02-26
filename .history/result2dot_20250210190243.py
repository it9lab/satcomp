import json
import ast

def cs2str(root, cs):
    # print(f"root={root}")
    res = []
    (i, j, ref) = root

    if j - i == 1:
        res.append(ref)
    else:
        children = cs[root]
        # print(f"root = {root}")
        # print(f"children = {children}")
        if ref == None: # SLPの生成規則を表す内部ノードの場合
            assert len(children) == 2 or (len(children) == 1 and children[0][2] == "RLrule")
            if children[0][2]  == "RLrule" and len(children) == 1:
                res += cs2str(children[0], cs)
            else:
                res += cs2str(children[0], cs)
                res += cs2str(children[1], cs)
        elif str(ref).startswith("RLrule") == True: # 連帳圧縮ルールの繰り返しの一単位分を表す葉（または内部）ノードの場合
            assert len(children) == 2
            # print(f"children_RLrule = {children}")
            for j in range(int((children[1][1] - children[0][0]) / (children[0][1] - children[0][0]))):
                res += cs2str(children[0], cs)

        else: # 葉ノードの場合
            # print(f"root = {root}")
            # print(f"children_leaves = {children}")
            assert children == None
            # 参照しているノードが連長圧縮全体のノード，SLPルールのノード，文字で場合分けしたい
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
        data_str = json.load(file)

    data_dict = json.loads(data_str)

    # factors部分を抜き出し、辞書型に変換
    factors_str = data_dict["factors"]
    root, factors = ast.literal_eval(factors_str)
    print(f"factors = {factors}")

    # テキストを復元
    int_list = cs2str(root, factors)
    text = ""
    for i in range(len(int_list)):
        text += chr(int_list[i])
    print(f"text = {text}")

    # factorsの辞書型をdot言語に変換
    node_dict = {}
    rule_dict = {}
    rank_str = "  {rank=same; "

    for key, value in factors.items():
        if value is None:
            node_dict[key] = f"  \"{key}\" [label={text[key[0]:key[1]]}];\n"
        else:
            rule_dict[key] = f"  \"{key}\" -> \"{value}\";\n"

    node_dict = dict(sorted(node_dict.items()))
    rule_dict = dict(sorted(rule_dict.items()))

    # dot言語に変換
    dot_str = "digraph G {\n"
    for key, value in node_dict.items():
        dot_str += value
    for key, value in rule_dict.items():
        dot_str += value
    dot_str += "}\n"

    # DOTファイルを書き込み
    with open('result.dot', 'w') as f:
        f.write(dot_str)

    # コマンドラインから以下を実行してPNGに変換
    # dot -Tpng tree.dot -o tree.png

if __name__ == "__main__":
    main()