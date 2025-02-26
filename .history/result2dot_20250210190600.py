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
        data_dict = json.load(file)
    

    # factors部分を抜き出し、辞書型に変換
    factors_str = data_dict["factors"]
    root, factors = ast.literal_eval(factors_str)

    # テキストを復元
    int_list = cs2str(root, factors)
    for i in range(len(int_list)):
        int_list[i] = chr(int_list[i])
    text = "".join(int_list)

    # factorsをdotファイルに変換
    dot_str = "digraph G {\n"
    rank_str = "  {rank=same; "
    for parent, children in factors.items():
        if children is None:
            dot_str += f'  "{parent}" [label="{text[parent[0]:parent[1]]}"];\n'
            rank_str += f'"{parent}"; '
        else:
            dot_str += f'  "{parent}" -> "{children[0]}";\n'
            dot_str += f'  "{parent}" -> "{children[1]}";\n'
    rank_str += "}\n"
    dot_str += rank_str
    dot_str += "  ordering=out;\n"
    dot_str += "}\n"

    # DOTファイルを書き込み
    with open('tree.dot', 'w') as f:
        f.write(dot_str)

if __name__ == "__main__":
    main()