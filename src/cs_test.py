import os
import sys
import random
import argparse
import ast
from typing import Optional
import time

from pysat.card import CardEnc
from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

import subprocess

from cs_solver import smallest_CollageSystem
from rlslp_solver import smallest_RLSLP
from slp_solver import smallest_SLP
from slp import SLPExp

SIZE_W = 2
TIME_W = 9
TIME_PREC = 4

# ファクターをツリー構造で可視化
def factors2img(factors: dict, solver_type: str, text: str) -> int:

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

    size = num_phrases - 2 + alphabet_size + num_csref

    dot_str += rank_str
    dot_str += "  ordering=out;\n"
    dot_str += "}\n"


    # ディレクトリ作成
    os.makedirs("for_cs_test/outputs", exist_ok=True)
    os.makedirs(f"for_cs_test/outputs/{text}", exist_ok=True)

    # DOTファイルを書き込み
    with open(f"for_cs_test/outputs/{text}/{solver_type}.dot", "w", encoding="utf-8") as f:
        f.write(dot_str)

    subprocess.run([
        "dot", "-Tpng",
        f"for_cs_test/outputs/{text}/{solver_type}.dot",
        "-o", f"for_cs_test/outputs/{text}/{solver_type}.png",
    ])
    # os.system('dot -Tpng result.dot -o result/' + text + '.png')

    return size

# すべての文法圧縮による最小文字列分解を実行し，結果を比較
def run_all_solvers(text: bytes):
    # input("Press Enter key to start the loop...")
    print(f"Input text: {text.decode('utf-8')}")

    size = {}
    time_prep = {}
    time_total = {}

    for solver_type in ["CS", "RLSLP", "SLP"]: 
        sol_factors = {}

        exp = SLPExp.create()

        if solver_type == "CS":
            # t0 = time.perf_counter()
            sol_factors = smallest_CollageSystem(text, exp)
            # print(time.perf_counter() - t0)

        elif solver_type == "RLSLP":
            sol_factors = smallest_RLSLP(text, exp)

        else:
            sol_factors = smallest_SLP(text, exp)
        
        root, factors = ast.literal_eval(str(sol_factors))
        
        size[solver_type] = factors2img(factors, solver_type, text.decode("utf-8"))
        time_prep[solver_type] = exp.time_prep
        time_total[solver_type] = exp.time_total
        assert size[solver_type] != exp.factor_size

        print(f"Smallest {solver_type.upper()} Size: {size[solver_type]}")

    return size, time_prep, time_total

def evaluate_sizes(text: bytes, size: dict, score: dict = {"SLP":0, "RLSLP":0, "CS":0, "total":0}):
    log_string = ""
    # error: CS > RLSLP SLP
    if size["CS"] > size["SLP"] or size["CS"] > size["RLSLP"]:
        print("CS is larger than SLP or RLSLP size.")
        log_string += "   Bad: "

    # error: RLSLP > SLP
    elif size["RLSLP"] > size["SLP"]:
        print("RLSLP is larger than SLP size.")
        log_string += " BadRL: "

    # success: CS <= RLSLP <= SLP
    # success: CS = RLSLP <= SLP
    elif size["CS"] == size["RLSLP"]:
        score["RLSLP"] += 1
        log_string += "Normal: "

    # success: CS < RLSLP <= SLP
    else:
        print("CS size is the smallest.")
        score["CS"] += 1
        log_string += f"-{size['RLSLP']-size['CS']}Good: "

    log_string += f"{text.decode('utf-8')}, Smallest CS: {size['CS']:{SIZE_W}}|RLSLP: {size['RLSLP']:{SIZE_W}}|SLP: {size['SLP']:{SIZE_W}},"

    with open("for_cs_test/cs_test_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(log_string)

    score["total"] += 1

def print_times(time_prep: dict, time_total: dict):
    print(f" time_prep : SLP {time_prep['SLP']:{TIME_W}.{TIME_PREC}f}, RLSLP {time_prep['RLSLP']:{TIME_W}.{TIME_PREC}f}, CS {time_prep['CS']:{TIME_W}.{TIME_PREC}f}")
    print(f"time_total : SLP {time_total['SLP']:{TIME_W}.{TIME_PREC}f}, RLSLP {time_total['RLSLP']:{TIME_W}.{TIME_PREC}f}, CS {time_total['CS']:{TIME_W}.{TIME_PREC}f}")

    log_string = ""
    # 実行時間をログに記録
    log_string += f" Time_prep CS: {time_prep['CS']:{TIME_W}.{TIME_PREC}f}|RLSLP: {time_prep['RLSLP']:{TIME_W}.{TIME_PREC}f}|SLP: {time_prep['SLP']:{TIME_W}.{TIME_PREC}f},"
    log_string += f" Time_total CS: {time_total['CS']:{TIME_W}.{TIME_PREC}f}|RLSLP: {time_total['RLSLP']:{TIME_W}.{TIME_PREC}f}|SLP: {time_total['SLP']:{TIME_W}.{TIME_PREC}f}\n"
    with open("for_cs_test/cs_test_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(log_string)

# スコアを表示
def print_scores(score: dict):
    print(f"number of attempts : {score['total']}")
    print(f"score : SLP {score['SLP']}, RLSLP {score['RLSLP']}, CS {score['CS']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Compute Minimum Internal Collage System.")
    parser.add_argument("--str", type=str, help="input string", default="")
    parser.add_argument("--random", type=int, help="length of random string", default=0)
    args = parser.parse_args()

    return args

if __name__ == "__main__":
    args = parse_args()

    if args.str != "":
        text = bytes(args.str, "utf-8")

        size, tprep, ttotal = run_all_solvers(text)
        evaluate_sizes(text, size)
        print_times(tprep, ttotal)

    elif args.random:
        score = {"SLP":0, "RLSLP":0, "CS":0, "total":0}
        while True:
            text = bytes("".join(random.choices("ABC", k=args.random)), "utf-8")

            size, tprep, ttotal = run_all_solvers(text)
            evaluate_sizes(text, size, score)
            print_times(tprep, ttotal)
            print_scores(score)

            print("-" * 40)
    else:
        print("Please provide either --str or --random argument.")