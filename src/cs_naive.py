import argparse
import copy
import json
import os
import sys
import time
from logging import CRITICAL, DEBUG, INFO, Formatter, StreamHandler, getLogger

from attractor_bench_format import AttractorExp

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
FORMAT = "[%(lineno)s - %(funcName)10s() ] %(message)s"
formatter = Formatter(FORMAT)
handler.setFormatter(formatter)
logger.addHandler(handler)

##############################################################################################
# Code by rici
# https://stackoverflow.com/questions/14900693/enumerate-all-full-labeled-binary-tree
#
# A very simple representation for Nodes. Leaves are anything which is not a Node.


class Node(object):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __repr__(self):
        return "(%s %s)" % (self.left, self.right)

# SLP分解を全探索的に行う関数
def enum_ordered(labels):
    if len(labels) == 1:
        yield labels[0] # 関数を一時的に実行停止させる
    else:
        for i in range(1, len(labels)):
            for left in enum_ordered(labels[:i]):
                for right in enum_ordered(labels[i:]):
                    yield Node(left, right)


##############################################################################################


def minimize_tree(root, nodedic, rlcounter):
    if type(root) == Node: # ノードの場合
        # (root, left, right, rlite, rlcounter)を返す
        # left:rootの左の子ノード
        # right:rootの右の子ノード
        # rlcounter:蓮長圧縮ルールの生成規則であれば1，そうでなければ0を格納
        # rlite:繰り返して表現している文字列or文字を格納
        left, leftofleft, rightofleft, rlite1, rlcounter1 = minimize_tree(root.left, nodedic, rlcounter)
        right, leftofright, rightofright, rlite2, rlcounter2 = minimize_tree(root.right, nodedic, rlcounter)
        # 生成規則がある場合
        if (left, right) in nodedic: # (left, right)となる生成規則がある場合
            if rlite1 == rlite2: # 参照する生成規則が蓮長圧縮ルールの場合
                rlite = rlite1
                rlcounter = 1
            else:
                rlite = None
                rlcounter = 0
             
            res = nodedic[left, right]
            return res, left, right, rlite, rlcounter

        else: # 生成規則がない場合
            if rlcounter1 == 1 and rlcounter2 == 1: # 左右のノードが連長圧縮ルールである
                if rlite1 == rlite2: # 同じ繰り返しを用いていた
                    rlite = rlite1
                    rlcounter = 1
                    return root, left, right, rlite, rlcounter
                else:
                    rlcounter = 0
                    nodedic[left, right] = root
                    nodedic[leftofleft, rightofleft] = left
                    nodedic[leftofright, rightofright] = right
                    return root, left, right, None, rlcounter
                
            elif rlcounter1 == 1 and rlcounter2 == 0: # 左ノードのみが蓮長圧縮ルール
                if rlite1 == right:
                    rlcounter = 1
                    rlite = rlite1
                    return root, left, right, rlite, rlcounter
                else:
                    rlcounter = 0
                    nodedic[left, right] = root
                    nodedic[leftofleft, rightofleft] = left
                    return root, left, right, None, rlcounter
                
            elif rlcounter1 == 0 and rlcounter2 == 1: # 右ノードのみが蓮長圧縮ルール
                if rlite2 == left:
                    rlcounter = 1
                    rlite = rlite2
                    return root, left, right, rlite, rlcounter
                else:
                    rlcounter = 0
                    nodedic[left, right] = root
                    nodedic[leftofleft, rightofleft] = right
                    return root, left, right, None, rlcounter
                
            elif rlcounter1 == 0 and rlcounter2 == 0: # 左右のノードが連長圧縮ルールでない
                if left == right: # 生成規則がXXの場合 
                    rlcounter = 1
                    rlite = left
                    return root, right, left, rlite, rlcounter
                else: # 生成規則がXYの場合
                    nodedic[left, right] = root
                    return root, right, left, None, rlcounter
        
    else: # 文字の場合
        # print(type(root))
        if root not in nodedic:
            nodedic[root] = root
            rlite = root
        else:
            rlite = root
        return root, None, None, rlite, rlcounter
        
# パーサの作成
# type:引数の型を指定
# help:引数の説明
# default:何も入力されなかった時に入力される費
def parse_args():
    parser = argparse.ArgumentParser(description="Compute Minimum RLSLP.")
    parser.add_argument("--file", type=str, help="input file", default="") # 第１引数
    parser.add_argument("--str", type=str, help="input string", default="") # 第２引数
    parser.add_argument("--output", type=str, help="output file", default="") # 第３引数
    parser.add_argument(
        "--log_level",
        type=str,
        help="log level, DEBUG/INFO/CRITICAL",
        default="CRITICAL",
    )
    args = parser.parse_args() # 引数の解析
    if args.file == "" and args.str == "":
        parser.print_help() # プログラムのヘルプを開く
        sys.exit()
    return args


if __name__ == "__main__":
    args = parse_args()

    if args.str != "":
        text = bytes(args.str, "utf-8")

    else:
        text = open(args.file, "rb").read()

    if args.log_level == "DEBUG":
        logger.setLevel(DEBUG)
    elif args.log_level == "INFO":
        logger.setLevel(INFO)
    elif args.log_level == "CRITICAL":
        logger.setLevel(CRITICAL)

    exp = AttractorExp.create()
    exp.algo = "rlslp-naive"
    exp.file_name = os.path.basename(args.file)
    exp.file_len = len(text)

    total_start = time.time()

    minsz = len(text) * 2 # SLPの生成規則の最小サイズ
    ming = None # 最小サイズ時の生成規則
    solutioncounter = 0 # 試行回数
    for tree in enum_ordered(text):
        solutioncounter += 1
        logger.info(tree) # 構文木を表示する
        nodedic = {} # 生成規則を列挙した辞書型データ
        rlcounter = 0
        rt, rtleft, rtright, rtrlite, rtrlcounter = minimize_tree(tree, nodedic, rlcounter) # 文字列分解に対応する生成規則を生成
        sz = len(nodedic)
        if sz < minsz: # 最小サイズを更新する
            minsz = sz
            ming = copy.deepcopy(nodedic)

    exp.time_total = time.time() - total_start
    exp.time_prep = exp.time_total
    exp.factor_size = minsz
    exp.sol_nvars = solutioncounter

    print("minimum RLSLP size = %s" % minsz)
    print("grammar: %s" % ming)

    if args.output == "":
        print(exp.to_json(ensure_ascii=False))  # type: ignore
    else:
        with open(args.output, "w") as f:
            json.dump(exp, f, ensure_ascii=False)
