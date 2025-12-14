import json
import ast
import sys
import subprocess

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/json2img.py [solver_type(slp/rlslp/cs)] [string]")
        sys.exit(1)
    solver_type = sys.argv[1]
    text = sys.argv[2]

    # solverを実行して，結果をjson形式で取得
    solve = subprocess.run(["pipenv", "run", "python", "src/" + solver_type + "_solver.py", "--str", text], capture_output=True, text=True)
    solveout = ''.join(solve.stdout.splitlines())
    data_dict = json.loads(solveout)

    # textとfactor_sizeを出力
    print(text)
    print(data_dict["factor_size"])

    # factors部分を抜き出し、辞書型に変換
    factor_size = data_dict["factor_size"]
    factors_str = data_dict["factors"]
    root, factors = ast.literal_eval(factors_str)

    # factorsをdotファイルに変換
    dot_str = "digraph G {\n"
    rank_nodes = []  # Collect nodes with their starting index for ordering
    num_csref = 0

    dot_str += "  graph [splines=polyline];\n"  # Use polyline edges for clarity

    # Process parent nodes in the order of their appearance in the text
    for parent, children in sorted(factors.items(), key=lambda x: x[0][0]):
        if children is None:
            pass
            # if not isinstance(parent[2], tuple):
            #     dot_str += f'  "{parent}" [label="{text[parent[0]:parent[1]]}"];\n'
            #     rank_nodes.append((str(parent), parent[0]))
        else:
            # Process children in order of their starting position
            for c in sorted(children, key=lambda x: x[0]):
                # 切断規則の場合
                if isinstance(c[2], tuple):
                    dot_str += f'  "{parent}" -> "{c[2]}";\n'
                    dot_str += f'  "{c[2]}" -> "{num_csref}"[label="Collage"];\n'
                    dot_str += f'  "{num_csref}" [label="{text[c[0]:c[1]]}"];\n'
                    assert text[c[0]:c[1]] == text[c[2][2]+c[2][0]:c[2][2]+c[2][0]+(c[1]-c[0])]
                    rank_nodes.append((str(num_csref), c[0]))
                    num_csref += 1
                elif c[2] == "RestRL":
                    dot_str += f'  "{parent}" -> "{c}" [label="RestRL"];\n'
                    dot_str += f'  "{c}" [label = "{text[c[0]:c[1]]}"];\n'
                    rank_nodes.append((str(c), c[0]))
                elif c[2] is None or c[2] == "RLrule":
                    dot_str += f'  "{parent}" -> "{c}";\n'
                elif c[2] < len(text):
                    dot_str += f'  "{parent}" -> "{c}" [label="SLP{c[2],c[2]+c[1]-c[0]}"];\n'
                    dot_str+= f'  "{c}" [label = "{text[c[0]:c[1]]}"];\n'
                    rank_nodes.append((str(c), c[0]))
                else:
                    assert c[2] >= len(text)
                    dot_str += f'  "{parent}" -> "{c}";\n'
                    dot_str+= f'  "{c}" [label = "{text[c[0]]}"];\n'
                    rank_nodes.append((str(c), c[0]))
                # else:
                #     if c[1] - c[0] == 1 or c[2] == 'RLrule' or c[2] == None:
                #         dot_str += f'  "{parent}" -> "{c}";\n'
                #     elif parent[2] == 'RLrule' and parent[0] == c[2]:
                #         dot_str += f'  "{parent}" -> "{c}" [label="RestRL"];\n'
                #     else:
                #         dot_str += f'  "{parent}" -> "{c}" [label="SLP{c[2],c[2]+c[1]-c[0]}"];\n'

    # Sort the collected nodes by their starting index to match the text order
    rank_nodes_sorted = sorted(rank_nodes, key=lambda item: item[1])
    rank_str = "  {rank=same; " + " ".join(f'"{node}"' for (node, _) in rank_nodes_sorted) + " }\n"
    
    dot_str += rank_str
    dot_str += "  ordering=out;\n"
    dot_str += "}\n"

    # DOTファイルを書き込み
    with open('dot/'+solver_type+'_json.dot', 'w') as f:
        f.write(dot_str)

    # DOTファイルをPNGファイルに変換
    subprocess.run(["dot", "-Tpng", "dot/"+solver_type+"_json.dot", "-o", "img/"+solver_type+".png"])
    # os.system('dot -Tpng result.dot -o result/' + text + '.png')