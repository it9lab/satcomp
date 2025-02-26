import json
import ast

def cs2str(root, cs):
    res = []
    (i, j, ref) = root

    if j - i == 1:
        res.append(ref)
    else:
        children = cs[root]
        if ref == None:
            assert len(children) == 2 or (len(children) == 1 and children[0][2] == "RLrule")
            if children[0][2] == "RLrule" and len(children) == 1:
                res += cs2str(children[0], cs)
            else:
                res += cs2str(children[0], cs)
                res += cs2str(children[1], cs)
        elif str(ref).startswith("RLrule") == True:
            assert len(children) == 2
            for j in range(int((children[1][1] - children[0][0]) / (children[0][1] - children[0][0]))):
                res += cs2str(children[0], cs)
        else:
            assert children == None
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

    # テキストを復元
    text_list = cs2str(root, factors)
    for i in range(len(text_list)):
        text_list[i] = chr(text_list[i])
    text = "".join(text_list)

    # factorsをdotファイルに変換
    dot_str = "digraph G {\n"
    rank_str = "  {rank=same; "
    num_csref = 0
    for parent, children in factors.items():
        if children is None:
            dot_str += f'  "{parent}" [label="{text[parent[0]:parent[1]]}"];\n'
            rank_str += f'"{parent}"; '
        else:
            for c in children:
                if isinstance(c[2], tuple):
                    dot_str += f'  "{parent}" -> "{c[2]}";\n'
                    dot_str += f' "{c[2]}" -> "{num_csref}";\n'
                    dot_str += f' "{num_csref}" [label="{text[c[0][0]:c[0][1]]}"];\n'
                    num_csref += 1
                    rank_str += f'"{c[0]}"; '
                else:
                    dot_str += f'  "{parent}" -> "{c[0]}";\n'
    rank_str += "}\n"
    dot_str += rank_str
    dot_str += "  ordering=out;\n"
    dot_str += "}\n"

    # DOTファイルを書き込み
    with open('result.dot', 'w') as f:
        f.write(dot_str)

    # DOTファイルをPNGファイルに変換
    import os
    os.system('dot -Tpng result.dot -o result.png')

if __name__ == "__main__":
    main()