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
    rank_nodes = []  # Collect nodes with their starting index for ordering
    num_csref = 0

    # Process parent nodes in the order of their appearance in the text
    for parent, children in sorted(factors.items(), key=lambda x: x[0][0]):
        if children is None:
            if not isinstance(parent[2], tuple):
                dot_str += f'  "{parent}" [label="{text[parent[0]:parent[1]]}"];\n'
                rank_nodes.append((str(parent), parent[0]))
        else:
            # Process children in order of their starting position
            for c in sorted(children, key=lambda x: x[0]):
                if isinstance(c[2], tuple):
                    dot_str += f'  "{parent}" -> "{c[2]}"[label="Collage"];\n'
                    dot_str += f'  "{c[2]}" -> "{num_csref}";\n'
                    dot_str += f'  "{num_csref}" [label="{text[c[0]:c[1]]}"];\n'
                    assert text[c[0]:c[1]] == text[c[2][2]+c[2][0]:c[2][2]+c[2][0]+(c[1]-c[0])]
                    rank_nodes.append((str(num_csref), c[0]))
                    num_csref += 1
                else:
                    if parent[2] == 'RLrule':
                        dot_str += f'  "{parent}" -> "{c}" [label="RLSLP{()^}"];\n'
                    elif c[1] - c[0] != 1 and c[2] is not None:
                        dot_str += f'  "{parent}" -> "{c}" [label="SLP{c[2],c[2]+c[1]-c[0]}"];\n'
                    else:
                        dot_str += f'  "{parent}" -> "{c}";\n'

    # Sort the collected nodes by their starting index to match the text order
    rank_nodes_sorted = sorted(rank_nodes, key=lambda item: item[1])
    rank_str = "  {rank=same; " + " ".join(f'"{node}"' for (node, _) in rank_nodes_sorted) + " }\n"
    
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