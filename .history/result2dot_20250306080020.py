import json
import ast
import sys
import subprocess

# csの生成規則から文字列を復元する関数
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
                for (refi, refj, refref) in cs.keys():
                    if ref[0] == refi and ref[1] == refj:
                        n = (refi, refj, refref)
                        res += cs2str(n, cs)[ref[2]:ref[2]+(j-i)]
                        break
            elif (ref, ref + j - i, None) in cs:
                n = (ref, ref + j - i, None)
                res += cs2str(n, cs)
            else:
                n = (ref, ref + j - i, "RLrule")
                res += cs2str(n, cs)
    return res

if __name__ == "__main__":
    # 引数


    # cs_solver.pyを実行して，標準出力を取得
    subprocess.run(["python", "src/cs_solver.py", "--str", "abc"], capture_output=True, text=True)

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
                    dot_str += f'  "{parent}" -> "{c[2]}";\n'
                    dot_str += f'  "{c[2]}" -> "{num_csref}"[label="Collage"];\n'
                    dot_str += f'  "{num_csref}" [label="{text[c[0]:c[1]]}"];\n'
                    assert text[c[0]:c[1]] == text[c[2][2]+c[2][0]:c[2][2]+c[2][0]+(c[1]-c[0])]
                    rank_nodes.append((str(num_csref), c[0]))
                    num_csref += 1
                else:
                    if c[1] - c[0] == 1 or c[2] == 'RLrule' or c[2] == None:
                        dot_str += f'  "{parent}" -> "{c}";\n'
                    elif parent[2] == 'RLrule' and parent[0] == c[2]:
                        dot_str += f'  "{parent}" -> "{c}" [label="RestRL"];\n'
                    else:
                        dot_str += f'  "{parent}" -> "{c}" [label="SLP{c[2],c[2]+c[1]-c[0]}"];\n'

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
    # os.system('dot -Tpng result.dot -o result/' + text + '.png')

if __name__ == "__main__":
    main()