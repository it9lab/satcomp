import os
import sys
import random
import argparse
from logging import CRITICAL, DEBUG, INFO, Formatter, StreamHandler, getLogger
from typing import Optional, Union
import json
import ast

from pysat.card import CardEnc
from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

import subprocess
from slp import SLPExp, SLPType

from cs_solver import smallest_CollageSystem, CSExp
from rlslp_solver import smallest_RLSLP
from slp_solver import smallest_SLP

# ファクターをツリー構造で可視化
def factors2img(factors: dict, solver_type: str, text: Union[str, bytes]):
    name = text.decode("utf-8") if isinstance(text, (bytes, bytearray)) else text

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

    num_phrases = len(rank_nodes_sorted)
    alphabet_size = len(set(text))

    size = num_phrases + alphabet_size + num_csref - 2

    dot_str += rank_str
    dot_str += "  ordering=out;\n"
    dot_str += "}\n"


    # ディレクトリ作成
    os.makedirs("for_cs_test/outputs", exist_ok=True)
    os.makedirs(f"for_cs_test/outputs/{name}", exist_ok=True)

    # DOTファイルを書き込み
    with open(f"for_cs_test/outputs/{name}/{solver_type}.dot", "w", encoding="utf-8") as f:
        f.write(dot_str)

    subprocess.run([
        "dot", "-Tpng",
        f"for_cs_test/outputs/{name}/{solver_type}.dot",
        "-o", f"for_cs_test/outputs/{name}/{solver_type}.png",
    ])
    # os.system('dot -Tpng result.dot -o result/' + text + '.png')

    return size

# すべての文法圧縮による最小文字列分解を実行し，結果を比較
def run_all_solvers(text: bytes, score: dict = {"slp":0, "rlslp":0, "cs":0, "total":0}):
    # input("Press Enter key to start the loop...")
    print(f"string : {text}")

    size = {}
    for solver_type in ["cs", "rlslp", "slp"]: 
        sol_factors = {}

        if solver_type == "cs":
            sol_factors = smallest_CollageSystem(text)
        elif solver_type == "rlslp":
            sol_factors = smallest_RLSLP(text)
        else:
            sol_factors = smallest_SLP(text)
        
        root, factors = ast.literal_eval(str(sol_factors))
        
        size[solver_type] = factors2img(factors, solver_type, text.decode("utf-8"))

        if solver_type != "cs":
            print(f"{solver_type} size : {size[solver_type]}")
        else:
            print(f"{solver_type} size : {size[solver_type]}")

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size["cs"] > size["slp"] or size["cs"] > size["rlslp"]:
        print("cs is larger than SLP or RLSLP size.")

        os.makedirs("for_cs_test/log", exist_ok=True)
        with open('for_cs_test/log/error.log', 'a') as f:
            f.write(text.decode("utf-8") + ',' +
                    " cs:" + str(size["cs"]) + 
                    " rlslp:" + str(size["rlslp"]) +  
                    " slp:" + str(size["slp"]) + "\n")

    # Collage Systemのサイズが最も小さいとき
    elif size["cs"] < size["slp"] and size["cs"] < size["rlslp"]:
        score["cs"] += 1
        print("cs is the smallest.")

        os.makedirs("for_cs_test/log", exist_ok=True)
        with open('for_cs_test/log/good.log', 'a') as f:
            f.write(text.decode("utf-8") + ',' +
                    " cs:" + str(size["cs"]) + 
                    " rlslp:" + str(size["rlslp"]) +  
                    " slp:" + str(size["slp"]) + "\n")
    
    elif size["cs"] == size["rlslp"] and size["rlslp"] < size["slp"]:
        score["rlslp"] += 1

        os.makedirs("for_cs_test/log", exist_ok=True)
        with open('for_cs_test/log/other.log', 'a') as f:
            f.write(text.decode("utf-8") + ',' +
                    " cs:" + str(size["cs"]) + 
                    " rlslp:" + str(size["rlslp"]) +  
                    " slp:" + str(size["slp"]) + "\n")
    
    else:
        score["slp"] += 1 

        os.makedirs("for_cs_test/log", exist_ok=True)
        with open('for_cs_test/log/other.log', 'a') as f:
            f.write(text.decode("utf-8") + ',' +
                    " cs:" + str(size["cs"]) + 
                    " rlslp:" + str(size["rlslp"]) +  
                    " slp:" + str(size["slp"]) + "\n")
    
    score["total"] += 1

# スコアを表示
def print_score(score: dict):
    print(f"score : SLP {score['slp']}, RLSLP {score['rlslp']}, CS {score['cs']}")
    print(f"total : {score['total']}")
    print("-" * 40)

def parse_args():
    parser = argparse.ArgumentParser(description="Compute Minimum Internal Collage System.")
    parser.add_argument("--str", type=str, help="input string", default="")
    parser.add_argument("--random", action="store_true", help="use random string")
    args = parser.parse_args()
    if args.str == True and args.str == "":
        parser.print_help()
        sys.exit()

    return args

if __name__ == "__main__":
    args = parse_args() # 解析するデータの指定

    text = bytes()
    if args.str != "":
        text = bytes(args.str, "utf-8")
        run_all_solvers(text)
    elif args.random:
        while True:
            text = bytes("".join(random.choices("AB", k=40)), "utf-8")
            score = {"slp":0, "rlslp":0, "cs":0, "total":0}
            run_all_solvers(text, score)
            print_score(score)