import argparse
import functools
import json
import os
import sys
import time
from enum import auto
from logging import CRITICAL, DEBUG, INFO, Formatter, StreamHandler, getLogger
from typing import Optional

from pysat.card import CardEnc
from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

import subprocess

from mysat import (
    Enum,
    Literal,
    LiteralManager,
    pysat_and,
    pysat_atleast_one,
    pysat_if,
    pysat_iff,
    pysat_name_cnf,
    pysat_or,
)
from slp import SLPExp, SLPType

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
FORMAT = "[%(lineno)s - %(funcName)10s() ] %(message)s"
formatter = Formatter(FORMAT)
handler.setFormatter(formatter)
logger.addHandler(handler)

#CollageSystemLiteralという列挙型のクラスの定義
class CollageSystemLiteral(Enum):
    true = Literal.true             #true = 1
    false = Literal.false           #false = 2
    auxlit = Literal.auxlit         #auxlit = 3
    phrase = auto()  # (i,l) (representing T[i:i+l)) is phrase of grammar parsing
    pstart = auto()  # i is a starting position of a phrase of grammar parsing
    slpref = auto()  # (j,i,l): phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
    rlref = auto() # (j,i,l): phrase (j,j+l) references (T[i,i+l))*(t-1)  ((T[i,i+l])*(t-1) <- T[j,j+l])
    csref = auto() # (j,i,l): phrase (j,j+l) references (T[i,i+l))  ((T[i,i+l]) <- T[j,j+l])
    dref = auto()
    referred = auto()  # (i,l): T[i,i+l) is referenced by some phrase
    depth = auto()
                         # "T[i,i+l) is referenced by some phrase" or
                         # "T[i,i+l) is labeled by a run-length non-terminal" or
                         # "[i,i+l) is the left child of a run-length rule" or
                         # "T[i,i+l) is labeled by a truncation non-terminal"


class CollageSystemLiteralManager(LiteralManager):
    """
    Manage literals used for solvers.
    """

    def __init__(self, text: bytes):
        self.text = text
        self.n = len(self.text)
        self.lits = CollageSystemLiteral
        self.verifyf = {
            CollageSystemLiteral.phrase: self.verify_phrase,
            CollageSystemLiteral.pstart: self.verify_pstart,
            CollageSystemLiteral.slpref: self.verify_slpref,
            CollageSystemLiteral.rlref: self.verify_rlref,
            CollageSystemLiteral.csref: self.verify_csref,
            CollageSystemLiteral.dref: self.verify_dref,
            CollageSystemLiteral.depth: self.verify_depth,
            CollageSystemLiteral.referred: self.verify_referred,
        }
        super().__init__(self.lits) # type: ignore

    # 新しくIDを割り当てるメソッド
    def newid(self, *obj) -> int:
        res = super().newid(*obj)
        if len(obj) > 0 and obj[0] in self.verifyf:
            self.verifyf[obj[0]](*obj)
        return res

    # 変数がf_{i1,j1}の型であるか確認するメソッド
    def verify_phrase(self, *obj):
        # obj = (name, i, l) (representing T[i:i+l)) is phrase of grammar parsing
        assert len(obj) == 3
        name, i, l = obj
        assert name == self.lits.phrase
        assert 0 <= i < self.n
        assert 0 < l <= self.n
        assert i + l <= self.n

    # 変数がp_iの型であるか確認するメソッド
    def verify_pstart(self, *obj):
        # print(f"verify_pstart, {obj}")
        # obj = (name, i) i is a starting position of a phrase of grammar parsing
        assert len(obj) == 2
        name, i = obj
        assert name == self.lits.pstart
        assert 0 <= i <= self.n #i \in [1,n+1]

    # 変数がref_{i<-j,l}の型であるか確認するメソッド
    def verify_slpref(self, *obj):
        # print(f"verify_ref, {obj}")
        # obj = (name, j, i, l) phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
        assert len(obj) == 4
        name, j, i, l = obj
        assert name == self.lits.slpref
        assert 0 <= i < self.n-1 #i \in [1,n-1]
        assert j < j + l <= i < i + l <= self.n
        assert 1 < l <= self.n

    # 変数がref^r_{i<-j,l}の型であるか確認するメソッド
    def verify_rlref(self, *obj):
        # print(f"verify_rlref, {obj}")
        # obj = (name, j, i, l) phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
        assert len(obj) == 4
        name, j, i, l = obj
        assert name == self.lits.rlref
        assert 0 <= j < self.n
        assert j < i < j + l < i + l <= self.n
        assert 1 < l <= self.n

    # 変数がref^c_{j,l2<-i,l1}の型であるか確認するメソッド
    def verify_csref(self, *obj):
        # print(f"verify_csref, {obj}")
        # obj = (name, i1, j1, i2, j2) phrase (i1,j1) refers to T[i2,j2);  T[i1,j1) -> T[i2,j2);
        assert len(obj) == 5
        name, j, l2, i, l1 = obj
        assert name == self.lits.csref
        assert 0 <= i < self.n
        assert 0 <= j < self.n
        assert 1 < l1 <= self.n
        assert 1 < l2 <= self.n
        assert i + l1 <= self.n
        assert j + l2 <= self.n
        assert i + l1 <= j or j + l2 <= i

    # 変数がdref_{ j,l <- i }の型であるか確認するメソッド
    def verify_dref(self, *obj):
        assert len(obj) == 4
        name, j, l, i = obj
        assert name == self.lits.dref
        assert 0 <= i < self.n
        assert 0 <= j < self.n
        assert 0 < l <= self.n
        assert j + l <= self.n

    
    # 変数がdepth_{i,l,d}の型であるか確認するメソッド
    def verify_depth(self, *obj):
        assert len(obj) == 4
        name, i, l, d = obj
        assert name == self.lits.depth
        assert 0 <= i < self.n
        assert 0 < l <= self.n
        assert d >= 0

    # 変数がq_{j,l}の型であるか確認するメソッド
    def verify_referred(self, *obj):
        # print(f"verify_referred, {obj}")
        # obj = (name, i2, j2) T[i2,j2) is referenced by some phrase
        assert len(obj) == 3
        name, j, l = obj
        assert name == self.lits.referred
        assert 0 <= j < self.n
        assert 0 < l <= self.n
        assert j + l <= self.n

# # SLPルールにおける参照先の候補を格納する関数
# def compute_lpf(text: bytes):  # non-self-referencing lpf
#     """
#     lpf[i] = length of longest prefix of text[i:] that occurs in text[0:i]
#     """
#     #ここをtext[i:]のtext[0:i+t]中の最長接頭辞の長さに置き換えたい
#     n = len(text)
#     lpf = []
#     for i in range(0, n):
#         lpf.append(0)
#         for j in range(0, i):
#             l = 0
#             while j + l < i and i + l < n and text[i + l] == text[j + l]:
#                 l += 1
#             if l > lpf[i]:
#                 lpf[i] = l
#     #print(f"lpf = {lpf}")
#     return lpf


# # 連長圧縮ルールの参照先の候補のデータを格納する関数
# def compute_rllpf(text: bytes):
#     """
#     rllpf[i] = length of longest prefix of text[i:] that occurs in text[0:i+l]
#     """
#     n = len(text)
#     rllpf = []
#     for i in range(0, n-1):
#         rllpf.append(0)
#         for j in range(0, i):
#             l = 0
#             while j + l < i + l and i + l < n and text[i + l] == text[j + l]:
#                 l += 1
#             if l > rllpf[i]:
#                 rllpf[i] = l
#     # print(f"rllpf = {rllpf}")
#     return rllpf

# # 切り取り規則の参照先の候補のデータを格納する関数
# def compute_cslpf(text: bytes):
#     """
#     cslpf[i] = length of longest prefix of text[i:] that occurs in text except interval[i:i+l]
#     """
#     n = len(text)
#     cslpf = []
#     for i in range(0, n-1):
#         cslpf.append(0)
#         for j in range(0, n-1):
#             l = 0
#             while j + l < n and i + l < n and text[j + l] == text[i + l]:
#                 l += 1
#             if l > cslpf[i]:
#                 cslpf[i] = l
#     return cslpf

# 条件式を基に重み付きCNFの作成
def smallest_CollageSystem_WCNF(text: bytes):
    """
    Compute the max sat formula for computing the smallest SLP
    """
    n = len(text)
    logger.info(f"text length = {len(text)}") # テキストの長さをログ出力
    wcnf = WCNF() #空の重み付きCNFを生成

    lm = CollageSystemLiteralManager(text) # textに対して生成されるすべての変数からなる集合を表す.
    # print("sloooow algorithm for lpf... (should use linear time algorithm)")

    # lpf = compute_lpf(text)
    # rllpf = compute_rllpf(text)
    # cslpf = compute_cslpf(text)

    # defining the literals  ########################################
    # ref(i,j,l): defined for all i,j,l>1 s.t. T[i:i+l) = T[j:j+l)
    # pstart(i)
    # phrase(i,l) defined for all i, l > 1 with l <= lpf[i]
    phrases = []
    for i in range(0, n + 1):
        lm.newid(lm.lits.pstart, i)  # definition of p_i

    #ファクタになり得る変数の作成
    for i in range(0, n):
        #一文字のファクタ
        phrases.append((i, 1))
        for l in range(1, n - i + 1):
            for d in range(0, n+1):
                lm.newid(lm.lits.depth, i, l, d)
            # lm.newid(lm.lits.phrase, i, l)  # definition of f_{i,l}(type-A)

            """"
        for rll in range(1, max(2, rllpf[i] + 1)):
            phrases.append((i, rll))
            lm.newid(lm.lits.phrase, i, rll)  # definition of f_{i,l}(type-b)
        """

    #refの定義
    refs_by_slpreferred = {} #(j,l)(参照先の開始位置と区間長)がキー，i(参照元の開始位置)が値
    refs_by_slpreferrer = {} #(i,l)(参照元の開始位置と区間長)がキー，j(参照先の開始位置)が値

    for j in range(0, n):
        for i in range(j + 1, n):
            #print(lpf[j])
            for l in range(2, n - i + 1):
                if j + l <= i and text[j : j + l] == text[i : i + l]:
                    #print(f"{text[j:j+l]}, {text[i:i+l]}")
                    lm.newid(lm.lits.slpref, j, i, l)  # definition of ref_{j<-i,l}
                    if not (j, l) in refs_by_slpreferred:
                        refs_by_slpreferred[j, l] = []
                    refs_by_slpreferred[j, l].append(i) #キー[j,l]にiを格納する
                    if not (i, l) in refs_by_slpreferrer:
                        refs_by_slpreferrer[i, l] = []
                    refs_by_slpreferrer[i, l].append(j) #キー[i,l]にjを格納する

    #print(f"SLPの参照先 = {refs_by_slpreferred}")
    #print(f"SLPの参照元 = {refs_by_slpreferrer}")


    refs_by_allrule = {} # 連長圧縮ルール全体が表す区間の開始位置と区間長（キー），右のノードの開始位置（値）
    refs_by_rliterated = {} # 連長圧縮ルールの左のノードの開始位置と区間長（キー），右のノードが表す区間長（値）
    refs_by_rlreferrer = {} # 連長圧縮ルールの右のノードの開始位置と区間長（キー），左のノードの開始位置（値）
    
    #ref^rの定義
    for j in range(0, n):
        for i in range(j + 1, n):
            for l in range(2, n - i + 1):
                # 二つの文字列は，一部のみ重複かつ一致していて，重複していない部分の長さは文字列の長さを余り無しで割り切れる
                if i < j + l  and text[j : j + l] == text[i : i + l] and (l % (i - j)) == 0:
                    lm.newid(lm.lits.rlref, j, i, l)  # definition of {ref^r}_{j<-i,l}
                    #print(f"{text[j:i+l]},{text[j:i]},{text[i:i+l]}")
                    #print(f"全体{j, l+i-j}, 左の子{j, i-j}, 右の子{i, l}")
                    if not (j, l + i - j) in refs_by_allrule:
                        refs_by_allrule[j, l + i - j] = []
                    refs_by_allrule[j, l + i - j].append(i)
                    if not (j, i - j) in refs_by_rliterated:
                        refs_by_rliterated[j, i - j] = []
                    refs_by_rliterated[j, i - j].append(l)
                    if not (i, l) in refs_by_rlreferrer:
                        refs_by_rlreferrer[i, l] = []
                    refs_by_rlreferrer[i, l].append(j) # 参照先の位置を格納

    #print(f"連長圧縮ルール全体 = {refs_by_allrule}")
    #print("連長圧縮左のノード", refs_by_rliterated)
    #print("連帳圧縮右のノード", refs_by_rlreferrer)

    refs_by_csreferred = {} #(j,l2)(参照先)がキー，(i,l1)(参照元)が値
    refs_by_csreferrer = {} #(i,l1)(参照元)がキー，(j,l2)(参照先)が値

    #ref^cの定義
    for j in range(0, n):
        for i in range(j + 1, n):
            for l1 in range(2, n - i + 1):
                if j + l1 <= i and text[j : j + l1] == text[i : i + l1]:
                    # 右側が左側を参照するとき
                    #print(f"左参照　左側の文字列:{text[j:j+l1]} = 右側の文字列:{text[i:i+l1]}")
                    for substr_left in range(0, j + 1):
                        for substr_length in range(l1, i - substr_left + 1):
                            if j + l1 <= substr_left + substr_length <= i:
                                # print(text[j:j+l1], "<-", text[substr_left:substr_left+substr_length])
                                # print(j, j+l1, "<-", substr_left, substr_left+substr_length)
                                if not (substr_left, substr_length) in refs_by_csreferred:
                                    refs_by_csreferred[substr_left, substr_length] = []
                                refs_by_csreferred[substr_left, substr_length].append([i, l1]) #キー[j(substr_left), l2(substr_length)]にiを格納する
                                if not (i, l1) in refs_by_csreferrer:
                                    refs_by_csreferrer[i, l1] = []
                                refs_by_csreferrer[i, l1].append([substr_left, substr_length]) #キー[i,l1]にj(substr_left)を格納する
                                if not lm.contains(lm.lits.csref, substr_left, substr_length, i, l1):
                                    lm.newid(lm.lits.csref, substr_left, substr_length, i, l1) #definition of {ref^c}_{j,l2<-i,l1}
                    # 左側が右側を参照するとき
                    # print(f"右参照　左側の文字列:{text[j:j+l1]} = 右側の文字列:{text[i:i+l1]}")
                    for substr_left in range(j + l1, i + 1):
                        for substr_length in range(l1, n - substr_left + 1):
                            if i + l1 <= substr_left + substr_length <= n:
                                # print(text[substr_left:substr_left+substr_length], "->",text[j:j+l1])
                                # print(substr_left, substr_left+substr_length, "->", j, j+l1)
                                if not (substr_left, substr_length) in refs_by_csreferred:
                                    refs_by_csreferred[substr_left, substr_length] = []
                                refs_by_csreferred[substr_left, substr_length].append([j, l1]) #キー[j(substr_left), l2(substr_length)]にiを格納する
                                if not (j, l1) in refs_by_csreferrer:
                                    refs_by_csreferrer[j, l1] = []
                                refs_by_csreferrer[j, l1].append([substr_left, substr_length]) #キー[i,l1]にj(substr_left)を格納する                                    
                                if not lm.contains(lm.lits.csref, substr_left, substr_length, j, l1):
                                    lm.newid(lm.lits.csref, substr_left, substr_length, j, l1) #definition of {ref^c}_{j,l2<-i,l1}
                        #print("reset")
    # print(f"切り取り規則の参照先={refs_by_csreferred}")
    # print(f"切り取り規則を用いて導出される文字列={refs_by_csreferrer}")

    #qの定義
    nt_intervals = list(set(refs_by_slpreferred.keys())|set(refs_by_rliterated.keys())|set(refs_by_csreferred.keys())|set(refs_by_allrule.keys())) # intervals implying nonterminal
    for (j, l) in nt_intervals:
        lm.newid(lm.lits.referred, j, l)
    # drefの定義
    refs_by_allreferred = {}
    referred_keys = list(set(refs_by_slpreferred.keys())|set(refs_by_rliterated.keys())|set(refs_by_csreferred.keys()))
    for (j, l) in referred_keys:
        #print(f"[j, l] = {[j, l]}")
        #print(set([refs_by_csreferrer[i, l][x][0] for x in range(len(refs_by_csreferrer))]))
        if refs_by_slpreferred.get((j, l)):
            for i in refs_by_slpreferred[j, l]:
                if not (j, l) in refs_by_allreferred:
                    refs_by_allreferred[j, l] = []
                refs_by_allreferred[j, l].append(i)
        if refs_by_rliterated.get((j, l)):
            if not (j, l) in refs_by_allreferred:
                    refs_by_allreferred[j, l] = []
            refs_by_allreferred[j, l].append(j+l)
        if refs_by_csreferred.get((j, l)):
            for (i, l2) in refs_by_csreferred[j, l]:
                if not (j, l) in refs_by_allreferred:
                    refs_by_allreferred[j, l] = []
                refs_by_allreferred[j, l].append(i)
        refs_by_allreferred[j, l] = set(refs_by_allreferred[j, l])
        for i in refs_by_allreferred[j, l]:
            lm.newid(lm.lits.dref, j, l, i)
            #print([j, l], "←",i)
    #print(refs_by_allreferred.keys())

    # refの添え字のリストとref^rの添え字のリストを結合させ重複を除いたリスト(csrefを追加済み)
    refs_by_allreferrers = list(set(refs_by_slpreferrer.keys())|set(refs_by_rlreferrer.keys())|set(refs_by_csreferrer.keys()))

    # 二文字以上のファクタになりうる変数の組をphrasesに追加
    phrases.extend(refs_by_allreferrers)

    # print(f"refs_by_allreferrers = {refs_by_allreferrers}")
    
    # // start constraint (1)(2) ###############################
    # (1):phrase(i,l) <=> pstart[i] and pstart[i+l] and \neg{pstart[i+1]} and .. and \neg{pstart[i+l-1]}

    # 文字列の先頭と末尾は必ずファクタの開始位置である
    wcnf.append([lm.getid(lm.lits.pstart, 0)])
    wcnf.append([lm.getid(lm.lits.pstart, n)])

    for i in range(n):
        for l in range(1, n - i + 1):
            plst = [-lm.getid(lm.lits.pstart, (i + j)) for j in range(1, l)] + [
                lm.getid(lm.lits.pstart, i), #p_iの取得
                lm.getid(lm.lits.pstart, (i + l)), #p_(i+l)の取得
            ]
            lm.newid(lm.lits.phrase, i, l)
            #print(lm.getid(lm.lits.phrase, i, l), i, l)

        # range_iff_startp:plst全体を表すliteral
        # clauses:条件式(1)の右辺を表す
            range_iff_startp, clauses = pysat_and(lm.newid, plst)
            wcnf.extend(clauses)
            wcnf.extend(pysat_iff(lm.getid(lm.lits.phrase, i, l), range_iff_startp))
        # pysat_iff(x,y)->リスト[[-x,y], [x, -y]]を返す．(x<=>yを表現する関数)

     # (2):there must be at least one new phrase beginning from [i+1,...,i+max(1,lpf[i] or rllpf[i])]
    for i in range(n):
        for l in range(2, n - i + 1):
            if not (i,l) in phrases:
                #print(f"phrasesにないペア={i,l}")
                wcnf.append([-lm.getid(lm.lits.phrase, i, l)])
    """
    print(f"phrase = {phrases}")
    for (j,l) in phrases:
        # ref_(.<-i,l) or ref^r_(.<-i,l)を満たさない(i,l)となるf_(i,l)
        # 末尾 or i + lpf[i] < i + 1 +lpf[i+1]のとき
        if l > 1:
            if not (j,l) in refs_by_rlreferrer.keys():
                wcnf.append([-lm.getid(lm.lits.phrase, j, l)])
            if not (j,l) in refs_by_slpreferrer.keys():
                wcnf.append([-lm.getid(lm.lits.phrase, j, l)])
                    # wcnf.extend(-lm.getid(lm.lits.phrase, j, l))
    """
    """
                if (j,l) in phrases:
                    wcnf.append([-lm.getid(lm.lits.phrase, j, l)])
                    #wcnf.extend(-lm.getid(lm.lits.phrase, j, l))
    """
    """
        print(f"{i}回目")
        if i + 1 == n:
            print(f"lst = {lst}")
            lst = list(range(i + 1, i + max(1, lpf[i]) + 1))
            wcnf.append([lm.getid(lm.lits.pstart, i) for i in lst])

        elif lpf[i] - 1 < lpf[i + 1] and rllpf[i] - 1 < rllpf[i + 1]:
                rllst = list(range(i + 1, i + max(1, rllpf[i]) + 1))
                print(f"rllst = {rllst}")
                wcnf.append([lm.getid(lm.lits.pstart, i) for i in rllst])
                for j in [i, i+rllpf[i]]:
                    if rllpf[j] + 1 < rllpf[j+1]:
                        i = j
                        break
                    i = j
            # print(f"lst={lst}")
        elif lpf[i] - 1 < lpf[i + 1] and not rllpf[i] - 1 < rllpf[i + 1]:
            lst = list(range(i + 1, i + max(1, lpf[i]) + 1))
            wcnf.append([lm.getid(lm.lits.pstart, i) for i in lst])
            print(f"lst = {lst}")
                # print(f"rllst={rllst}")
        elif rllpf[i] - 1 < rllpf[i+1]:
            rllst = list(range(i + 1, i + max(1, rllpf[i]) + 1))
            print(f"rllst = {rllst}")
            wcnf.append([lm.getid(lm.lits.pstart, i) for i in rllst])
    """
    # // end constraint (1)(2) ###############################

    # // start constraint (3),(4) ###############################
    # (4):if phrase(j,l) = true there must be exactly one i < j such that ref(j,i,l) is true
    for (i, l) in refs_by_allreferrers:
        reflst1 = []
        reflst2 = []
        reflst3 = []
        #print(i,l)
        if (i,l) in refs_by_slpreferrer.keys():
            #print(f"nm(i, l) = {refs_by_slpreferrer[i, l], i, l}")
            reflst1 = [lm.getid(lm.lits.slpref, j, i, l) for j in refs_by_slpreferrer[i, l]]
        if (i,l) in refs_by_rlreferrer.keys():
            #print(f"rl(i, l) = {refs_by_rlreferrer[i, l], i, l}")
            reflst2 = [lm.getid(lm.lits.rlref, j, i, l) for j in refs_by_rlreferrer[i, l]]
        if (i,l) in refs_by_csreferrer.keys():
            # print(f"cs(i, l) = {i, l}")
            # print(refs_by_csreferrer[i, l])
            reflst3 = [lm.getid(lm.lits.csref, j, l2, i, l) for (j,l2) in refs_by_csreferrer[i, l]]
            # reflst3 = []
            # for (j, l2) in refs_by_csreferrer[i, l]:
            #     print(i, l, "->", j, l2)
            #     reflst3 = reflst3 + [lm.getid(lm.lits.csref, j, l2, i, l)]

        reflst = reflst1 + reflst2 + reflst3
        # reflst = list(set(reflst))
        # CardEnc.atmost(literalのリスト,閾値 k) -> "literalのリストの論理和 <= k"を表すリスト
        clauses = CardEnc.atmost(
            reflst,
            bound=1,
            vpool=lm.vpool,
        )
        wcnf.extend(clauses)

        # (3):ref_{・<-j,l}+ref^r{・<-j,l}+ref^c{・<-j,l}に対して,iが少なくとも一つが存在する.
        clause = pysat_atleast_one(reflst)

        # var_atleast:条件式(3)の右辺を表すliteral
        # clause_atleast:条件式(3)の右辺の節を表す
        var_atleast, clause_atleast = pysat_name_cnf(lm, [clause]) # この関数じゃなくていいかも？
        wcnf.extend(clause_atleast)
        phrase = lm.getid(lm.lits.phrase, i, l)
        wcnf.extend(pysat_iff(phrase, var_atleast))

    # // end constraint (3),(4) ###############################

    # # // start constraint (5) ###############################
    # # (5):referred(i,l) = true iff there is some j > i such that ref(j,i,l) = true
    # for (j, l) in refs_by_slpreferred.keys():
    #     assert l > 1
    #     ref_sources, clauses = pysat_or(
    #         lm.newid,
    #         [lm.getid(lm.lits.slpref, j, i, l) for i in refs_by_slpreferred[j, l]],
    #     )
    #     wcnf.extend(clauses)
    #     referredid = lm.getid(lm.lits.referred, i, l)
    #     wcnf.extend(
    #         pysat_iff(ref_sources, referredid)
    #     )
    # # // end constraint (5) ###############################
    
    # // start constraint (6) ###############################
    # (6):区間(i, i+l)が，連結規則に則って区間(j, j+l)を参照しているなら，f_(j, j+l)はファクタではなく，p_j, p_j+lはファクタの開始位置である
    # phrase(occ,l) is only defined if l <= lpf[occ] 
    for (j, l) in refs_by_slpreferred.keys():
        for i in refs_by_slpreferred[j, l]:
            qid = lm.getid(lm.lits.slpref, j, i, l)
            lst = [-qid] + [lm.getid(lm.lits.pstart, j + x) for x in range(1, l)]
            wcnf.append(lst)
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j + l)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.dref, j, l, i)))
    # // end constraint (6) ###############################

    # // start constraint (7) ###############################
    # (7):区間(i, i + l)が，連長圧縮規則に則って区間(j, i)を参照しているなら，位置rlreferer[j,l]はフレーズの開始位置となる
    for (j, l2) in refs_by_rliterated.keys():
        for l in refs_by_rliterated[j, l2]:
            # print(f"rlref(7) = {refs_by_rlreferrer}")
            # print(f"{text[j:i+l]}")
            qid = lm.getid(lm.lits.rlref, j, j+l2, l)
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.dref, j, l2, j+l2)))
    # // end constraint (7) ###############################

    # // start constraint () ###############################
    # ():区間(i, i + l1)が，切断規則に則って区間(j, j + l2)を参照しているなら，p_j, p_j+lはファクタの開始位置である
    for (j, l2) in refs_by_csreferred.keys():
        for (i, l1) in refs_by_csreferred[j, l2]:
            qid = lm.getid(lm.lits.csref, j, l2, i, l1)
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j + l2)))
            wcnf.append(pysat_if(qid, -lm.getid(lm.lits.phrase, j, l2)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.dref, j, l2, i)))
            # # 追加：切断規則は，連長圧縮規則の右側の子ノードのみを参照することはできない
            # if (j, l2) in refs_by_rlreferrer.keys():
            #     for j2 in refs_by_rlreferrer[j, l2]:
            #         wcnf.append([qid, -lm.getid(lm.lits.rlref, j2, j, l2)])
                

    # // end constraint () ###############################

    # // start constraint (8) ###############################
    # (8):qが真なら，qが表す区間を参照先に持つようなslpref, rlref, csref, またはその区間内に左右の子を共に含むrlrefが高々一つ存在する
    for (j, l) in nt_intervals:
        slpreferred_lst=[] # 連結規則の参照先のノードのidリスト
        rliterated_lst=[] # 連長圧縮規則の左の子ノード
        csreferred_lst=[] # 連結規則の参照先のノード
        allrule_lst=[] # 連長圧縮規則全体のノード

        if (j, l) in refs_by_slpreferred:
            for i in refs_by_slpreferred[j, l]:
                #print(f"slpref: ({j},{i},{l})")
                slpreferred_lst.append(lm.getid(lm.lits.slpref, j, i, l))

        if (j, l) in refs_by_rliterated:
            for l2 in refs_by_rliterated[j, l]:
                #print(f"rlref: ({j},{j+l},{j+l+l2})")
                rliterated_lst.append(lm.getid(lm.lits.rlref, j, j+l, l2))

        if (j, l) in refs_by_csreferred:
            for (i, l2) in refs_by_csreferred[j, l]:
                #print(f"csref: ({j},{l},{i},{l2})")
                csreferred_lst.append(lm.getid(lm.lits.csref, j, l, i, l2))
        
        if (j, l) in refs_by_allrule:
            for i in refs_by_allrule[j, l]:
                allrule_lst.append(lm.getid(lm.lits.rlref, j, i, l - i + j))
            

        referred_lst = []
        referred_lst.extend(slpreferred_lst + rliterated_lst + csreferred_lst + allrule_lst)
        # print(referred_lst)
        clause = pysat_atleast_one(referred_lst)
        var_refatleast, clause_refatleast = pysat_name_cnf(lm, [clause])
        wcnf.extend(clause_refatleast)
        referredid = lm.getid(lm.lits.referred, j, l)
        wcnf.extend(pysat_iff(referredid, var_refatleast))
    # // end constraint (8) #################################

    # // start constraint (9), (10) ###############################
    # (9):crossing intervals cannot be referred to at the same time.
    #rliterated = list(refs_by_rliterated)
    sorted_ntIntervals = [[] for _ in range(n)] # occ * n サイズのリストを作成
    for (occ, l) in nt_intervals:
        sorted_ntIntervals[occ].append(l)
    for lst in sorted_ntIntervals:
        lst.sort(reverse=True)
    # print(nt_intervals)
    # print(sorted_ntIntervals)

    for (occ1, l1) in nt_intervals:
        for occ2 in range(occ1 + 1, occ1 + l1):
            for l2 in sorted_ntIntervals[occ2]:
                if l2 == 1:
                    pass
                else:
                    #print(f"l1,l2,occ1,occ2 = {l1,l2,occ1,occ2}")
                    #print(occ1, occ2, occ1+l1, occ2+l2)
                    assert l1 > 1 and l2 > 1
                    assert occ1 < occ2 and occ2 < occ1 + l1
                    if occ1 + l1 >= occ2 + l2:
                        #print("ok")
                        break
                    #print("not ok")
                    id1 = lm.getid(lm.lits.referred, occ1, l1)
                    id2 = lm.getid(lm.lits.referred, occ2, l2)
                    wcnf.append([-id1, -id2])

    # // start constraint (11) ##############################
    # すべての文字の深さ，および文字列の深さは0以上であり，nより小さい
    for i in range(0,n):
        for l in range(1, n - i + 1):
            wcnf.append([lm.getid(lm.lits.depth, i, l, 0)])
            wcnf.append([-lm.getid(lm.lits.depth, i, l, n)])
    # // end constraint (11) ###############################

    # // start constraint (11) ##############################
    # depth_{i,l,d}=1ならば，depth_{i,l,d-1}である
    for i in range(0,n):
       for l in range(1, n - i + 1):
           for d in range(1,n):              
               wcnf.append(pysat_if(lm.getid(lm.lits.depth, i, l, d), lm.getid(lm.lits.depth, i, l, d-1)))
    # // end constraint (11) ###############################

    # // start constraint (11) ##############################
    #ともに同一のファクタ内に含まれるi-1, i番目の文字の深さは等しい
    for i in range(0,n-1):
        for d in range(0,n):
            id1 = lm.getid(lm.lits.pstart, i+1)
            id2 = lm.getid(lm.lits.depth, i, 1, d)
            id3 = lm.getid(lm.lits.depth, i+1, 1, d)
            # -1->23+(-2)(-3)
            # =1+23+(-2)(-3)
            # =1+(23+(-2))(23+(-3))
            # =1+((2+(-2))(3+(-2)))((2+(-3))(3+(-3)))
            # =1+(3+(-2))(2+(-3))
            # =(1+3+(-2))(1+2+(-3))
            wcnf.append([id1, -id2, id3])
            wcnf.append([id1, id2, -id3])


    # // end constraint (11) ###############################

    # // start constraint (11) ##############################
    #文字列の深さは，その文字列に含まれる文字の深さの最大値に等しい
    for i in range(0,n):
        for l in range(1, n - i + 1):
            for d in range(0,n):
                id1 = lm.getid(lm.lits.depth, i, l, d)
                list1 = [lm.getid(lm.lits.depth, k, 1, d) for k in range(i, i + l)]
                # (1->(2+3))((2+3)->1)
                # =(-1+(2+3))((-2)(-3)+1)
                # =(-1+2+3)(-2+1)(-3+1)
                # wcnf.append([-id1] + [id for id in list1])
                # for id in list1:
                #     wcnf.append([id1, -id])
                nvar, nclauses = pysat_or(lm.newid, list1)
                wcnf.extend(nclauses)
                wcnf.extend(pysat_iff(id1, nvar))

    # // end constraint (11) ###############################

    # // start constraint (11) ##############################
    #参照元の深さは参照先の深さより大きい
    for (j, l) in refs_by_allreferred.keys():
        for i in refs_by_allreferred[j, l]:
            id1 = lm.getid(lm.lits.dref, j, l, i)
            #番兵であるd=nを使う，d=nのとき，depth_{j,l,d}は必ず偽である
            for d in range(1,n+1):
                id2 = lm.getid(lm.lits.depth, i, 1, d)
                id3 = lm.getid(lm.lits.depth, j, l, d - 1)
                # 1->((-2)->(-3))
                # =1->(2+(-3))
                # =(-1)+(2+(-3))
                # =(-1)+2+(-3)
                wcnf.append([-id1, id2, -id3])

    # // end constraint (11) ############################### 


    '''
    # // start constraint (11) ##############################
    # 最初に出現した文字をファクタの開始位置とする
    for i in range(0, n):
        if lpf[i] == 0:
            wcnf.append([lm.getid(lm.lits.phrase, i, 1)])  # perhaps not needed
            pass

    # 初期設定:p_1,p_(n+1) = true
    wcnf.append([lm.getid(lm.lits.pstart, 0)])
    wcnf.append([lm.getid(lm.lits.pstart, n)])
    # // end constraint (11) ###############################
    '''

    # soft clauses: minimize # of phrases
    # soft clauseの作成
    for i in range(0, n):
        wcnf.append([-lm.getid(lm.lits.pstart, i)], weight=1)
    for (j, l2) in refs_by_csreferred:
        for (i, l1) in refs_by_csreferred[j, l2]:
            wcnf.append([-lm.getid(lm.lits.csref, j, l2, i, l1)], weight=1)
    return lm, wcnf, phrases, refs_by_slpreferrer, refs_by_rlreferrer, refs_by_csreferrer

# リストxとリストyの比較関数
# 1を返す → そのまま，0を返す → 順番を変える
def postorder_cmp(x, y):
    i1 = x[0]
    j1 = x[1]
    i2 = y[0]
    j2 = y[1]
    # print(f"compare: {x} vs {y}")
    if i1 == i2 and i2 == j2:
        return 0
    if j1 <= i2: # x < y
        return -1
    elif j2 <= i1: # y < x
        return 1
    elif i1 <= i2 and j2 <= j1: # y \subset x(yはbの部分区間)
        return 1
    elif i2 <= i1 and j1 <= j2: # x \subset y
        return -1
    else:
        assert False


# given a list of nodes that in postorder of subtree rooted at root,
# find the direct children of [root_i,root_j) and add it to slp
# slp[j,l,i] is a list of nodes that are direct children of [i,j)
#
def build_cs_aux(nodes, cs):
    root = nodes.pop()
    root_i = root[0]
    # root_j = root[1]
    # print(f"root = {root}")
    # print(f"root_i,root_j = {root_i},{root_j}")
    children = []
    while len(nodes) > 0 and nodes[-1][0] >= root_i:
        # print(f"nodes[-1] = {nodes[-1]}")
        c = build_cs_aux(nodes, cs)
        children.append(c)
    children.reverse() # 逆順に並び替える
    # assert len(children) <= 2
    cs[root] = children
    # print(f"cs[root] = {cs[root]}")
    ##########################################################
    return root

# turn multi-ary tree into binary tree
# 与えられた生成規則を基に復元する順番を決定する関数
def binarize_cs(root, cs):
    children = cs[root]
    # print(f"children = {children}")
    # 根ノードが連長圧縮の生成規則で表される
    numc = len(children)

    # print(f"numc = {numc}")
    # print(f"numc_children = {children}")
    # print(f"root_numc = {root}")
    assert numc == 0 or numc >= 2 or (numc == 1 and children[0][2] == "RLrule" or children[0][2] == "RLrule")

    if numc == 2:
        if children[1][2] == "RLrule":
            # children[1][2] = "RLrule" + str((children[1][1] - children[1][0]) / (children[0][1] - children[0][0])) + "times"
            cs[root] = (binarize_cs(children[0], cs), binarize_cs(children[1], cs))
        else:
            cs[root] = (binarize_cs(children[0], cs), binarize_cs(children[1], cs))
    
    elif numc == 1 and "RLrule" == children[0][2]:
        binarize_cs(children[0], cs)

    elif numc > 0:
        leftc = children[0]
        for i in range(1, len(children)):
            n = (root[0], children[i][1], None) if i < len(children) - 1 else root
            cs[n] = (leftc, children[i])
            leftc = n
        for c in children:
            binarize_cs(c, cs)

    else:
        cs[root] = None
    return root

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

# SLPの解析木の情報を保存
def recover_cs(text: bytes, pstartl, refs_by_slpreferrer, refs_by_rlreferrer, refs_by_csreferrer):
    n = len(text)
    # 各区間に対応するノードの種類を分類
    slpreferred = set((refs_by_slpreferrer[i, l], l) for (i, l) in refs_by_slpreferrer.keys()) # 参照元の位置と長さを保持するタプルを生成
    
    rliterated = set((refs_by_rlreferrer[i, l], i, l) for (i, l) in refs_by_rlreferrer.keys())

    csreferred = set((refs_by_csreferrer[i, l][0], refs_by_csreferrer[i, l][1]) for (i, l) in refs_by_csreferrer.keys()) # 参照元の位置と長さ

    # ノードが内部ノードかつ蓮長圧縮ルール全体のノードとみなされていた場合，連長圧縮ルール全体のノードとして扱う
    # 繰り返しを表す区間が左に出現していた時発生する

    # （葉ノードが表す区間，参照先のノードの開始位置）
    leaves = [(i, i + l, refs_by_slpreferrer[i, l]) for (i, l) in refs_by_slpreferrer.keys()]
    leaves.extend([(i, i + l, refs_by_rlreferrer[i, l]) for (i, l) in refs_by_rlreferrer.keys()])
    #切断規則は，（葉ノードが表す区間，（参照先の区間，参照する文字列の開始位置））
    leaves.extend([(i, i + l, (refs_by_csreferrer[i, l][0], refs_by_csreferrer[i, l][0] + refs_by_csreferrer[i, l][1], refs_by_csreferrer[i, l][2])) for (i, l) in refs_by_csreferrer.keys()])
    for i in range(len(pstartl) - 1):
        if pstartl[i + 1] - pstartl[i] == 1: # pstartl[i]が長さ1のファクタの開始位置の場合
            leaves.append((pstartl[i], pstartl[i + 1], text[pstartl[i]]))

    internal = [(occ, occ + l, None) for (occ, l) in slpreferred] # 内部ノードが表す区間(SLP)
    rlinternal = [(occ, i + l , "RLrule") for (occ, i, l) in rliterated] # 連長圧縮全体を表す内部ノードの区間(RLSLP)
    csinternal = [(occ, occ + l2, None) for (occ, l2) in csreferred] # 切り取り規則を表す内部ノードの区間(CS)
            # leaves = [(occ, j + l - i, None)]
            # print(f"occ, j, l = {occ, j, l}")
    for (j, l) in slpreferred:
        if (j, l) in csreferred:
            internal.remove((j, j + l, None))
        for (ri, rl) in refs_by_rlreferrer.keys():
            if j == refs_by_rlreferrer[ri, rl] and j + l == ri + rl:
                # print(f"i, l, j, rl={i,l,j,rl}")
                internal.remove((j, j + l, None))
    # # 連長圧縮規則の右側の子ノードが切断規則によって参照されている場合，それを内部ノードとして扱う必要はない，なぜならファクタであることが確定しているから
    # for (ri, rl) in refs_by_rlreferrer.keys():
    #     for (csi, csl) in csreferred:
    #         if ri == csi and rl == csl:
    #             csinternal.remove((csi, csi + csl, None))

    # print(f"slpreferred = {slpreferred}")
    # print(f"rliterated = {rliterated}")
    # print(f"csreferred = {csreferred}")
    # print(f"internal = {internal}")
    # print(f"rlinternal = {rlinternal}")
    # print(f"csinternal = {csinternal}")
    # print(f"leaves = {leaves}")
    nodes = leaves + internal + rlinternal + csinternal # 全てのノード情報が格納
    if len(nodes) > 1:
        nodes.append((0, n, None)) # 根ノードを表す区間を追加
    # print(f"nodes={nodes}")
    nodes.sort(key=functools.cmp_to_key(postorder_cmp)) # postorder_cmpの規則に従い，ソートする
    cs = {}
    root = build_cs_aux(nodes, cs)
    binarize_cs(root, cs)
    return (root, cs)

# 最小のSLPを計算,SLP分解したときの解析木を返す関数
def smallest_CollageSystem(text: bytes, exp: Optional[SLPExp] = None) -> SLPType:
    """
    Compute the smallest SLP.
    """
    total_start = time.time()
    lm, wcnf, phrases, refs_by_slpreferrer, refs_by_rlreferrer, refs_by_csreferrer = smallest_CollageSystem_WCNF(text) # 条件式を生成
    rc2 = RC2(wcnf) # MAX-SATを計算
    time_prep = time.time() - total_start  # 前処理時間
    sol_ = rc2.compute()    # MAX-SATの解を保持したint型のリストを返す．
    assert sol_ is not None
    sol = set(sol_)

    # print("sol:")
    # for x in sol:
    #     if x > 0:
    #         print(lm.id2str(x))

    n = len(text)

    posl = []
    for i in range(0, n + 1):
        x = lm.getid(lm.lits.pstart, i)
        if x in sol:
            posl.append(i)
    # print(f"posl={posl}")
    phrasel = []
    for (occ, l) in phrases:
        x = lm.getid(lm.lits.phrase, occ, l)
        if x in sol:
            phrasel.append((occ, occ + l))
    # print(f"phrasel={phrasel}")

    # dref = {}

    slprefs = {}
    for (i, l) in refs_by_slpreferrer.keys():
        for j in refs_by_slpreferrer[i, l]:
            if lm.getid(lm.lits.slpref, j, i, l) in sol:
                slprefs[i, l] = j
                assert lm.getid(lm.lits.dref, j, l, i) in sol
                # dref[j, l] = i
    # print(f"slprefs={slprefs}")
    # 連長圧縮ルールの参照先と参照元のデータを保存
    rlrefs = {}
    for (i, l) in refs_by_rlreferrer.keys():
        for j in refs_by_rlreferrer[i, l]:
            if lm.getid(lm.lits.rlref, j, i, l) in sol:
                rlrefs[i, l] = j
                assert lm.getid(lm.lits.dref, j, i - j, i) in sol
                # dref[j, i - j] = i
    # print(f"rlrefs={rlrefs}")
    csrefs = {}
    for (i, l1) in refs_by_csreferrer.keys():
        for (j, l2) in refs_by_csreferrer[i, l1]:
            if lm.getid(lm.lits.csref, j, l2, i, l1) in sol:
                for k in range(j, j + l2 - l1 + 1):
                    if text[i:i+l1] == text[k:k+l1]:
                        csrefs[i, l1] = (j, l2, k-j)
                assert lm.getid(lm.lits.dref, j, l2, i) in sol
                # dref[j, l2] = i

    depth = {}
    for i in range(0, n):
        for l in range(1, n - i + 1):
            assert lm.getid(lm.lits.depth, i, l, 0) in sol
            depth[i, l] = 0
            for d in range(1, n):
                if lm.getid(lm.lits.depth, i, l, d) in sol and d > depth[i, l]:
                    depth[i, l] = d

    # print(f"csrefs = {csrefs}")
    # MAX-SATの解からcsを生成
    root, cs = recover_cs(text, posl, slprefs, rlrefs, csrefs)
    # print(f"root={root}, cs = {cs}, cskeys={cs.keys()}") 

    cssize = len(posl) - 2 + len(set(text)) + len(csrefs) #RLSLPのサイズ+切断規則の数
    print(f"size: {cssize}")

    if exp:
        exp.time_total = time.time() - total_start
        exp.time_prep = time_prep
        exp.factors = f"{(root, cs)}"
        exp.factor_size = cssize  # len(internal_nodes) + len(set(text))
        exp.fill(wcnf)

    check = bytes(cs2str(root, cs))

    assert check == text

    return SLPType((root, cs))


def parse_args():
    parser = argparse.ArgumentParser(description="Compute Minimum SLP.")
    parser.add_argument("--file", type=str, help="input file", default="")
    parser.add_argument("--str", type=str, help="input string", default="")
    parser.add_argument("--output", type=str, help="output file", default="")
    parser.add_argument(
        "--size",
        type=int,
        help="exact size or upper bound of attractor size to search",
        default=0,
    )
    parser.add_argument(
        "--log_level",
        type=str,
        help="log level, DEBUG/INFO/CRITICAL",
        default="CRITICAL",
    )
    args = parser.parse_args()
    if args.file == "" and args.str == "":
        parser.print_help()
        sys.exit()

    return args


if __name__ == "__main__":
    # print("start!")
    args = parse_args() # 解析するデータの指定

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

    exp = SLPExp.create() # 出力したいフォーマットの作成
    exp.algo = "cs-sat"
    exp.file_name = os.path.basename(args.file)
    exp.file_len = len(text)

    collageSystem = smallest_CollageSystem(text, exp) # SLPの最小サイズを計算

    if args.output == "":
        with open("csdot", "w") as f:
            json.dump(exp.to_json(ensure_ascii=False), f, ensure_ascii=False) # type: ignore
        try:
            subprocess.run(["python", "result2dot.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing result2dot.py: {e}")

