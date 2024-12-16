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
    ref = auto()  # (j,i,l): phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
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
            CollageSystemLiteral.ref: self.verify_ref,
            CollageSystemLiteral.rlref: self.verify_rlref,
            CollageSystemLiteral.csref: self.verify_csref,
            CollageSystemLiteral.dref: self.verify_dref,
            CollageSystemLiteral.referred: self.verify_referred,
            CollageSystemLiteral.depth: self.verify_depth,
        }
        super().__init__(self.lits)

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
    def verify_ref(self, *obj):
        # print(f"verify_ref, {obj}")
        # obj = (name, j, i, l) phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
        assert len(obj) == 4
        name, j, i, l = obj
        assert name == self.lits.ref
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
        name, i, j, l = obj
        assert name == self.lits.dref
        assert 0 <= i < self.n
        assert 0 <= j < self.n
        assert 0 < l <= self.n
        assert j + l <= self.n

    
    # 変数がdepth_{i,l,d}の型であるか確認するメソッド
    def verify_depth(self, *obj):
        assert len(obj) == 4
        name, i, l, d == obj
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
        for l in range(1, n + 1):
            phrases.append((i, l))
            # lm.newid(lm.lits.phrase, i, l)  # definition of f_{i,l}(type-A)

            """"
        for rll in range(1, max(2, rllpf[i] + 1)):
            phrases.append((i, rll))
            lm.newid(lm.lits.phrase, i, rll)  # definition of f_{i,l}(type-b)
        """
    #refの定義
    refs_by_referred = {} #(j,l)(参照先の開始位置と区間長)がキー，i(参照元の開始位置)が値
    refs_by_referrer = {} #(i,l)(参照元の開始位置と区間長)がキー，j(参照先の開始位置)が値


    for j in range(0, n):
        for i in range(j + 1, n):
            #print(lpf[j])
            for l in range(2, n - i + 1):
                if j + l <= i and text[j : j + l] == text[i : i + l]:
                    print(f"{text[j:j+l]}, {text[i:i+l]}")
                    lm.newid(lm.lits.ref, j, i, l)  # definition of ref_{j<-i,l}
                    #lm.newid(lm.lits.dref, i, j, l) # definition of dref_{i->j,l}
                    if not (j, l) in refs_by_referred:
                        refs_by_referred[j, l] = []
                    refs_by_referred[j, l].append(i) #キー[j,l]にiを格納する
                    if not (i, l) in refs_by_referrer:
                        refs_by_referrer[i, l] = []
                    refs_by_referrer[i, l].append(j) #キー[i,l]にjを格納する

    print(f"SLPの参照先 = {refs_by_referred}")
    print(f"SLPの参照元 = {refs_by_referrer}")


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
                    print(f"{text[j:i+l]},{text[j:i]},{text[i:i+l]}")
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

    print(f"連長圧縮ルール全体 = {refs_by_allrule}")
    print("連長圧縮左のノード", refs_by_rliterated)
    print("連帳圧縮右のノード", refs_by_rlreferrer)

    refs_by_csreferred = {} #(j,l2)(参照先)がキー，(i,l1)(参照元)が値
    refs_by_csreferrer = {} #(i,l1)(参照元)がキー，(j,l2)(参照先)が値

    #ref^cの定義
    for i in range(n):
        for j in range(n):
            for l1 in range(2, n + 1):
                #...[i:i+l1]...[j:j+l1]..., [i:i+l1]==[j:j+l1]
                if i + l1 <= j and text[i : i + l1] == text[j : j + l1]:
                    for substr_left in range(i + l1, j + 1):
                        for substr_right in range(j + l1, n + 1):
                            substr_length = substr_right - substr_left
                            lm.newid(lm.lits.csref, substr_left, substr_length, i, l1) #definition of {ref^c}_{j,l2<-i,l1}
                            if not (substr_left, substr_length) in refs_by_csreferred:
                                refs_by_csreferred[substr_left, substr_length] = []
                            refs_by_csreferred[substr_left, substr_length].append([i, l1]) #キー[j(substr_left), l2(substr_length)]にiを格納する
                            if not (i, l1) in refs_by_csreferrer:
                                refs_by_csreferrer[i, l1] = []
                            refs_by_csreferrer[i, l1].append([substr_left, substr_length]) #キー[i,l1]にj(substr_left)を格納する
                #...[j:j+l1]...[i:i+l1]..., [j:j+l1]==[i:i+l1]
                elif j + l1 <= i and text[j : j + l1] == text[i : i + l1]:
                    for substr_left in range(0, j + 1):
                        for substr_right in range(j + l1, i + 1):
                            substr_length = substr_right - substr_left
                            lm.newid(lm.lits.csref, substr_left, substr_length, i, l1) #definition of {ref^c}_{j,l2<-i,l1}
                            if not (substr_left, substr_length) in refs_by_csreferred:
                                refs_by_csreferred[substr_left, substr_length] = []
                            refs_by_csreferred[substr_left, substr_length].append([i, l1]) #キー[j(substr_left), l2(substr_length)]にiを格納する
                            if not (i, l1) in refs_by_csreferrer:
                                refs_by_csreferrer[i, l1] = []
                            refs_by_csreferrer[i, l1].append([substr_left, substr_length]) #キー[i,l1]にj(substr_left)を格納する

    #print(f"切り取り規則の参照先={refs_by_csreferred}")
    #print(f"切り取り規則を用いて導出される文字列={refs_by_csreferrer}")

    #qの定義
    refs_by_allreferred = list(set(refs_by_referred.keys())|set(refs_by_rliterated.keys())|set(refs_by_csreferred.keys())|set(refs_by_allrule.keys()))
    for (j, l) in refs_by_allreferred:
        lm.newid(lm.lits.referred, j, l)

    # refの添え字のリストとref^rの添え字のリストを結合させ重複を除いたリスト(csrefを追加済み)
    refs_by_allreferrers = list(set(refs_by_referrer.keys())|set(refs_by_rlreferrer.keys())|set(refs_by_csreferrer.keys()))
    # print(f"refs_by_allreferrers = {refs_by_allreferrers}")

    # // start constraint (1)(2) ###############################
    # (1):phrase(i,l) <=> pstart[i] and pstart[i+l] and \neg{pstart[i+1]} and .. and \neg{pstart[i+l-1]}
    for i in range(n):
        for l in range( 1, n - i + 1):
            plst = [-lm.getid(lm.lits.pstart, (i + j)) for j in range(1, l)] + [
                lm.getid(lm.lits.pstart, i), #p_iの取得
                lm.getid(lm.lits.pstart, (i + l)), #p_(i+l)の取得
            ]
            lm.newid(lm.lits.phrase, i, l)

        # range_iff_startp:plst全体を表すliteral
        # clauses:条件式(1)の右辺を表す
            range_iff_startp, clauses = pysat_and(lm.newid, plst)
            wcnf.extend(clauses)
            wcnf.extend(pysat_iff(lm.getid(lm.lits.phrase, i, l), range_iff_startp))
        # pysat_iff(x,y)->リスト[[-x,y], [x, -y]]を返す．(x<=>yを表現する関数)

    # # (2):there must be at least one new phrase beginning from [i+1,...,i+max(1,lpf[i] or rllpf[i])]
    # for i in range(n):
    #     for l in range(1,n - i + 1):
    #         if not (i,l) in phrases:
    #             #print(f"phrasesにないペア={i,l}")
    #             wcnf.append([-lm.getid(lm.lits.phrase, i, l)])
    """
    print(f"phrase = {phrases}")
    for (j,l) in phrases:
        # ref_(.<-i,l) or ref^r_(.<-i,l)を満たさない(i,l)となるf_(i,l)
        # 末尾 or i + lpf[i] < i + 1 +lpf[i+1]のとき
        if l > 1:
            if not (j,l) in refs_by_rlreferrer.keys():
                wcnf.append([-lm.getid(lm.lits.phrase, j, l)])
            if not (j,l) in refs_by_referrer.keys():
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
        if (i,l) in refs_by_referrer.keys():
            #print(f"nm(i, l) = {refs_by_referrer[i, l], i, l}")
            reflst1 = [lm.getid(lm.lits.ref, j, i, l) for j in refs_by_referrer[i, l]]
        if (i,l) in refs_by_rlreferrer.keys():
            #print(f"rl(i, l) = {refs_by_rlreferrer[i, l], i, l}")
            reflst2 = [lm.getid(lm.lits.rlref, j, i, l) for j in refs_by_rlreferrer[i, l]]
        if (i,l) in refs_by_csreferrer.keys():
            #print(f"cs(i, l1) = {refs_by_csreferrer[i, l1], i, l1}")
            reflst3 = [lm.getid(lm.lits.csref, j, l2, i, l) for (j,l2) in refs_by_csreferrer[i, l]]

        reflst = reflst1 + reflst2 + reflst3

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
    # for (j, l) in refs_by_referred.keys():
    #     assert l > 1
    #     ref_sources, clauses = pysat_or(
    #         lm.newid,
    #         [lm.getid(lm.lits.ref, j, i, l) for i in refs_by_referred[j, l]],
    #     )
    #     wcnf.extend(clauses)
    #     referredid = lm.getid(lm.lits.referred, i, l)
    #     wcnf.extend(
    #         pysat_iff(ref_sources, referredid)
    #     )
    # # // end constraint (5) ###############################

    # // start constraint (6) ###############################
    # (6):if (occ,l) is a referred interval, it cannot be a phrase, but pstart[occ] and pstart[occ+l] must be true
    # phrase(occ,l) is only defined if l <= lpf[occ]
    referred = list(refs_by_referred.keys())
    for (j, l) in referred:
        if l > 1:
            qid = lm.getid(lm.lits.referred, j, l)
            lst = [-qid] + [lm.getid(lm.lits.pstart, j + x) for x in range(1, l)]
            wcnf.append(lst)
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, j + l)))
    # // end constraint (6) ###############################

    # // start constraint (7) ###############################
    # (7):区間(j, j + l)が区間(i,j)を繰り返して参照していれば，位置rlreferer[j,l]はフレーズの開始位置となる
    for (i, l) in refs_by_rlreferrer.keys():
        for j in refs_by_rlreferrer[i, l]:
            # print(f"rlref(7) = {refs_by_rlreferrer}")
            # print(f"{text[j:i+l]}")
            wcnf.append(
                pysat_if(
                    lm.getid(lm.lits.rlref, j, i, l),
                    lm.getid(lm.lits.pstart, j)
                )
            )
    # // start constraint (7) ###############################

    

    # // start constraint (8) ###############################
    # (8):q'の定義
    for (i, l) in refs_by_rliterated:
        referredlst=[] #q_{i,l}
        rlreflst1=[] # 連長圧縮ルール全体からなるノードのリスト
        rlreflst2=[] # 連長圧縮ルールの左のノードのリスト
        rliteratedlst=[]

        if (i, l) in refs_by_referred:
            referredlst.append(lm.getid(lm.lits.referred, i, l))

        for j in range(n):
            # 連長圧縮ルール全体
            # print(f"i,l,j = {i,l,j}")
            # print(f"allrule = {refs_by_allrule}")
            if (i,l) in refs_by_allrule.keys() and j in refs_by_allrule[i,l]:
                # print(f"rlref_all(8) = {i,j,i + l - j}")
                rlreflst1.append(lm.getid(lm.lits.rlref, j, i, i + l - j))

            # 連長圧縮ルールの左のノード
            if (i, l) in refs_by_rliterated.keys() and j == i + l:
                for rll in refs_by_rliterated[i, l]:
                    # print(f"rlref_left(8) = {i,j,rll}")
                    rlreflst2.append(lm.getid(lm.lits.rlref, j, i, rll))

        rliteratedlst.extend(referredlst + rlreflst1 + rlreflst2)

        clause = pysat_atleast_one(rliteratedlst)
        var_refatleast, clause_refatleast = pysat_name_cnf(lm, [clause])
        wcnf.extend(clause_refatleast)
        rliteratedid = lm.getid(lm.lits.rliterated, i, l)
        wcnf.extend(pysat_iff(rliteratedid, var_refatleast))
    # // end constraint (8) #################################

    # // start constraint (9), (10) ###############################
    # (9):crossing intervals cannot be referred to at the same time.
    #rliterated = list(refs_by_rliterated)
    rliterated_by_bp = [[] for _ in range(n)] # occ * n サイズのリストを作成
    for (occ, l) in refs_by_rliterated:
        rliterated_by_bp[occ].append(l)
    for lst in rliterated_by_bp:
        lst.sort(reverse=True)

    for (occ1, l1) in refs_by_rliterated:
        for occ2 in range(occ1 + 1, occ1 + l1):
            for l2 in rliterated_by_bp[occ2]:
                if l2 == 1:
                    pass
                else:
                    # print(f"l1,l2,occ1,occ2 = {l1,l2,occ1,occ2}")
                    assert l1 > 1 and l2 > 1
                    assert occ1 < occ2 and occ2 < occ1 + l1
                    if occ1 + l1 >= occ2 + l2:
                        break
                    id1 = lm.getid(lm.lits.rliterated, occ1, l1)
                    id2 = lm.getid(lm.lits.rliterated, occ2, l2)
                    wcnf.append([-id1, -id2])
    # (10):csreferrerの区間とq'の区間が重ならない時，csreferredの区間とq'が一部のみ重複する
    for (occ1_i, l1) in refs_by_csreferred.keys():   #csreferred {occ1_j <- occ1_i, l1}
        jlst = refs_by_csreferred[occ1_i, l1]
        for occ1_j in jlst:
            for (occ2, l2) in refs_by_rliterated:        #rliterated occ2, l2
                if l2 == 1:
                    pass
                else:
                    assert l1 > 1 and l2 > 1
                    if occ2 < occ1_j < occ2 + l2 < occ1_j + l1 or occ1_j < occ2 < occ1_j + l1 < occ2 + l2:
                        if occ2 <= occ1_i < occ1_i + l1 <= occ2 + l2:
                            id1 = lm.getid(lm.lits.csref, occ1_j, occ1_i, l1)
                            id2 = lm.getid(lm.lits.rliterated, occ2, l2)
                            wcnf.append([-id1,-id2])

    # // end constraint (9), (10) ###############################

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

    # soft clauses: minimize # of phrases
    # soft clauseの作成
    for i in range(0, n):
        wcnf.append([-lm.getid(lm.lits.pstart, i)], weight=1)
    return lm, wcnf, phrases, refs_by_referrer, refs_by_rlreferrer, refs_by_csreferrer

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
def build_rlslp_aux(nodes, rlslp):
    root = nodes.pop()
    root_i = root[0]
    # root_j = root[1]
    # print(f"root = {root}")
    # print(f"root_i,root_j = {root_i},{root_j}")
    children = []
    while len(nodes) > 0 and nodes[-1][0] >= root_i:
        # print(f"nodes[-1] = {nodes[-1]}")
        c = build_rlslp_aux(nodes, rlslp)
        children.append(c)
    children.reverse() # 逆順に並び替える
    rlslp[root] = children
    # print(f"rlslp[root] = {rlslp[root]}")
    ##########################################################
    return root

# turn multi-ary tree into binary tree
# 与えられた生成規則を基に復元する順番を決定する関数
def binarize_rlslp(root, rlslp):
    children = rlslp[root]
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
            rlslp[root] = (binarize_rlslp(children[0], rlslp), binarize_rlslp(children[1], rlslp))
        else:
            rlslp[root] = (binarize_rlslp(children[0], rlslp), binarize_rlslp(children[1], rlslp))

    elif numc > 0:
        leftc = children[0]
        for i in range(1, len(children)):
            n = (root[0], children[i][1], None) if i < len(children) - 1 else root
            rlslp[n] = (leftc, children[i])
            leftc = n
        for c in children:
            binarize_rlslp(c, rlslp)

    elif numc == 1 and "RLrule" == children[0][2]:
        binarize_rlslp(children[0], rlslp)

    else:
        rlslp[root] = None
    return root

# RLSLPの生成規則から文字列を復元する関数
def cs2str(root, rlslp):
    # print(f"root={root}")
    res = []
    (i, j, ref) = root

    if j - i == 1:
        res.append(ref)
    else:
        children = rlslp[root]
        # print(f"root = {root}")
        # print(f"children = {children}")
        if ref is None: # SLPの生成規則を表す内部ノードの場合
            assert len(children) == 2 or (len(children) == 1 and children[0][2] == "RLrule")
            if children[0][2]  == "RLrule" and len(children) == 1:
                res += cs2str(children[0], rlslp)
            else:
                res += cs2str(children[0], rlslp)
                res += cs2str(children[1], rlslp)
        elif str(ref).startswith("RLrule") == True: # 連帳圧縮ルールの繰り返しを表した葉ノードの場合
            assert len(children) == 2
            # print(f"children_RLrule = {children}")
            for j in range(int((children[1][1] - children[0][0]) / (children[0][1] - children[0][0]))):
                res += cs2str(children[0], rlslp)

        else: # 葉ノードの場合
            # print(f"root = {root}")
            # print(f"children_leaves = {children}")
            assert children is None
            # 参照しているノードが連長圧縮全体のノード，SLPルールのノード，文字で場合分けしたい
            if (ref, ref + j - i, None) in rlslp:
                n = (ref, ref + j - i, None)
            else:
                n = (ref, ref + j - i, "RLrule")

            res += cs2str(n, rlslp)
    return res

# SLPの解析木の情報を保存
def recover_rlslp(text: bytes, pstartl, refs_by_referrer, refs_by_rlreferrer, refs_by_csreferrer):
    n = len(text)
    # 各区間に対応するノードの種類を分類
    referred = set((refs_by_referrer[j, l], l) for (j, l) in refs_by_referrer.keys()) # 参照元の位置と長さを保持するタプルを生成

    if len(refs_by_rlreferrer) > 0:
        rliterated = set((refs_by_rlreferrer[j, l], j, l) for (j, l) in refs_by_rlreferrer.keys())
    else:
        rliterated = set()

    # 切り取り規則を用いているかどうか
    if len(refs_by_csreferrer) > 0:
        # csreferredに(i, j, l)のペアを入れていく
        csreferred = set((refs_by_csreferrer[j, l], j, l) for (j, l) in refs_by_csreferrer.keys())
        # print(csreferred)
    else:
        csreferred = set()

    # ノードが内部ノードかつ蓮長圧縮ルール全体のノードとみなされていた場合，連長圧縮ルール全体のノードとして扱う
    # 繰り返しを表す区間が左に出現していた時発生する
    # 切り取り規則においては，leavesにreferrerを入れるのみ
    leaves = [(j, j + l, refs_by_referrer[j, l]) for (j, l) in refs_by_referrer.keys()] + [(j, j + l, refs_by_rlreferrer[j, l]) for (j, l) in refs_by_rlreferrer.keys()] + [(j, j + l, refs_by_csreferrer[j, l]) for (j, l) in refs_by_csreferrer.keys()]# 葉ノードが表す区間
    for i in range(len(pstartl) - 1):
        if pstartl[i + 1] - pstartl[i] == 1: # pstartl[i]が長さ1のファクタの開始位置の場合
            leaves.append((pstartl[i], pstartl[i + 1], text[pstartl[i]]))

    internal = [(occ, occ + l, None) for (occ, l) in referred] # 内部ノードが表す区間(SLP)
    rlinternal = [(occ, j + l , "RLrule") for (occ, j, l) in rliterated] # 連長圧縮全体を表す内部ノードの区間(RLSLP)
            # leaves = [(occ, j + l - i, None)]
            # print(f"occ, j, l = {occ, j, l}")
    for (i, l) in referred:
        for (j, rl) in refs_by_rlreferrer.keys():
            if i == refs_by_rlreferrer[j, rl] and i + l == j + rl:
                # print(f"i, l, j, rl={i,l,j,rl}")
                internal.remove((i, i + l, None))

    print(f"referred = {referred}")
    print(f"rliterated = {rliterated}")
    print(f"internal = {internal}")
    print(f"rlinternal = {rlinternal}")
    print(f"leaves = {leaves}")
    nodes = leaves + internal + rlinternal # 全てのノード情報が格納
    if len(nodes) > 1:
        nodes.append((0, n, None)) # 根ノードを表す区間を追加
    # print(f"nodes={nodes}")
    nodes.sort(key=functools.cmp_to_key(postorder_cmp)) # postorder_cmpの規則に従い，ソートする
    rlslp = {}
    root = build_rlslp_aux(nodes, rlslp)
    binarize_rlslp(root, rlslp)
    return (root, rlslp)

# 最小のSLPを計算,SLP分解したときの解析木を返す関数
def smallest_CollageSystem(text: bytes, exp: Optional[SLPExp] = None) -> SLPType:
    """
    Compute the smallest SLP.
    """
    total_start = time.time()
    lm, wcnf, phrases, refs_by_referrer, refs_by_rlreferrer, refs_by_csreferrer = smallest_CollageSystem_WCNF(text) # 条件式を生成
    rc2 = RC2(wcnf) # MAX-SATを計算
    time_prep = time.time() - total_start  # 前処理時間
    sol_ = rc2.compute()    # MAX-SATの解を保持したint型のリストを返す．
    assert sol_ is not None
    sol = set(sol_)

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
    refs = {}
    for (j, l) in refs_by_referrer.keys():
        for i in refs_by_referrer[j, l]:
            if lm.getid(lm.lits.ref, j, i, l) in sol:
                refs[j, l] = i
    # print(f"refs={refs}")
    # 連長圧縮ルールの参照先と参照元のデータを保存
    rlrefs = {}
    for (j, l) in refs_by_rlreferrer.keys():
        for i in refs_by_rlreferrer[j, l]:
            if lm.getid(lm.lits.rlref, j, i, l) in sol:
                rlrefs[j, l] = i
    # print(f"rlrefs={rlrefs}")
    csrefs = {}
    for (j, l) in refs_by_csreferrer.keys():
        for i in refs_by_csreferrer[j, l]:
            if lm.getid(lm.lits.csref, j, i, l) in sol:
                csrefs[j, l] = i
    # print(f"csrefs = {csrefs}")
    # MAX-SATの解からRLSLPを生成
    root, rlslp = recover_rlslp(text, posl, refs, rlrefs, csrefs)
    # print(f"root={root}, rlslp = {rlslp}, rlslpkeys={rlslp.keys()}")

    rlslpsize = len(posl) - 2 + len(set(text))

    if exp:
        exp.time_total = time.time() - total_start
        exp.time_prep = time_prep
        exp.factors = f"{(root, rlslp)}"
        exp.factor_size = rlslpsize  # len(internal_nodes) + len(set(text))
        exp.fill(wcnf)

    check = bytes(cs2str(root, rlslp))

    assert check == text

    return SLPType((root, rlslp))


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
    print("start!")
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
    exp.algo = "rlslp-sat"
    exp.file_name = os.path.basename(args.file)
    exp.file_len = len(text)

    collageSystem = smallest_CollageSystem(text, exp) # SLPの最小サイズを計算

    if args.output == "":
        print(exp.to_json(ensure_ascii=False))  # type: ignore
    else:
        with open(args.output, "w") as f:
            json.dump(exp, f, ensure_ascii=False)
