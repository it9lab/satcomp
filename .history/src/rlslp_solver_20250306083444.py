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

#SLPLiteralという列挙型のクラスの定義
class RLSLPLiteral(Enum):
    true = Literal.true             #true = 1
    false = Literal.false           #false = 2
    auxlit = Literal.auxlit         #auxlit = 3
    phrase = auto()  # (i,l) (representing T[i:i+l)) is phrase of grammar parsing
    pstart = auto()  # i is a starting position of a phrase of grammar parsing
    ref = auto()  # (j,i,l): phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
    rlref = auto() # (j,i,l): phrase (j,j+l) references (T[i,i+l))*(t-1)  ((T[i,i+l])*(t-1) <- T[j,j+l])
    referred = auto()  # (i,l): T[i,i+l) is referenced by some phrase
    rlreferred = auto()  # (i,l):  One of the three condition is implied,
                         # "T[i,i+l) is referenced by some phrase" or
                         # "T[i,i+l) is labeled by a run-length non-terminal" or
                         # "[i,i+l) is the left child of a run-length rule"


class RLSLPLiteralManager(LiteralManager):
    """
    Manage literals used for solvers.
    """

    def __init__(self, text: bytes):
        self.text = text
        self.n = len(self.text)
        self.lits = RLSLPLiteral
        self.verifyf = {
            RLSLPLiteral.phrase: self.verify_phrase,
            RLSLPLiteral.pstart: self.verify_pstart,
            RLSLPLiteral.ref: self.verify_ref,
            RLSLPLiteral.rlref: self.verify_rlref,
            RLSLPLiteral.referred: self.verify_referred,
            RLSLPLiteral.rlreferred: self.verify_rlreferred,
        }
        super().__init__(self.lits)

    # 新しくIDを割り当てるメソッド
    def newid(self, *obj) -> int:
        res = super().newid(*obj)
        if len(obj) > 0 and obj[0] in self.verifyf:
            self.verifyf[obj[0]](*obj)
        return res

    # 変数がf_{i,l}の型であるか確認するメソッド
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
        assert i < i + l <= j < j + l <= self.n
        assert 1 < l <= self.n

    # 変数がref^r_{i<-j,l}の型であるか確認するメソッド
    def verify_rlref(self, *obj):
        # print(f"verify_rlref, {obj}")
        # obj = (name, j, i, l) phrase (j,j+l) references T[i,i+l)  (T[i,i+l] <- T[j,j+l])
        assert len(obj) == 4
        name, j, i, l = obj
        assert name == self.lits.rlref
        assert 0 <= i < self.n
        assert i < j < i + l < j + l <= self.n
        assert 1 < l <= self.n

    # 変数がq_{i,l}の型であるか確認するメソッド
    def verify_referred(self, *obj):
        # print(f"verify_referred, {obj}")
        # obj = (name, i, l) T[i,i+l) is referenced by some phrase
        assert len(obj) == 3
        name, i, l = obj
        assert name == self.lits.referred
        assert 0 <= i < self.n
        assert 0 < l <= self.n
        assert i + l <= self.n

    # 変数がq'_{i,l}の型であるか確認するメソッド
    def verify_rlreferred(self, *obj):
        # print(f"verify_rlreferred, {obj}")
        # obj = (name, i, l) T[i,i+l) is referenced by some phrase,
        # labeled by a run-length non-terminal, or the left child of a run-length rule.
        assert len(obj) == 3
        name, i, l = obj
        assert name == self.lits.rlreferred
        assert 0 <= i < self.n
        assert 0 < l <= self.n
        assert i + l <= self.n

# SLPルールにおける参照先の候補を格納する関数
def compute_lpf(text: bytes):  # non-self-referencing lpf
    """
    lpf[i] = length of longest prefix of text[i:] that occurs in text[0:i]
    """
    #ここをtext[i:]のtext[0:i+t]中の最長接頭辞の長さに置き換えたい
    n = len(text)
    lpf = []
    for i in range(0, n):
        lpf.append(0)
        for j in range(0, i):
            l = 0
            while j + l < i and i + l < n and text[i + l] == text[j + l]:
                l += 1
            if l > lpf[i]:
                lpf[i] = l
    # print(f"lpf = {lpf}")
    return lpf


# 連長圧縮ルールの参照先の候補のデータを格納する関数
def compute_rllpf(text: bytes):
    """
    rllpf[i] = length of longest prefix of text[i:] that occurs in text[0:i+l]
    """
    n = len(text)
    rllpf = []
    for i in range(0, n):
        rllpf.append(0)
        for j in range(0, i):
            l = 0
            while j + l < i + l and i + l < n and text[i + l] == text[j + l]:
                l += 1
            if l > rllpf[i]:
                rllpf[i] = l
    # print(f"rllpf = {rllpf}")
    return rllpf

# 条件式を基に重み付きCNFの作成
def smallest_RLSLP_WCNF(text: bytes):
    """
    Compute the max sat formula for computing the smallest SLP
    """
    n = len(text)
    logger.info(f"text length = {len(text)}") # テキストの長さをログ出力
    wcnf = WCNF() #空の重み付きCNFを生成

    lm = RLSLPLiteralManager(text) # textに対して生成されるすべての変数からなる集合を表す.
    # print("sloooow algorithm for lpf... (should use linear time algorithm)")
    lpf = compute_lpf(text)
    rllpf = compute_rllpf(text)

    # defining the literals  ########################################
    # ref(i,j,l): defined for all i,j,l>1 s.t. T[i:i+l) = T[j:j+l)
    # pstart(i)
    # phrase(i,l) defined for all i, l > 1 with l <= lpf[i]
    phrases = []
    for i in range(n + 1):
        lm.newid(lm.lits.pstart, i)  # definition of p_i

    #タイプA or タイプBのフレーズになり得る変数の作成
    for i in range(n):
        for l in range(1, max(2, lpf[i] + 1)):
            phrases.append((i, l))
            # lm.newid(lm.lits.phrase, i, l)  # definition of f_{i,l}(type-A)

            """"
        for rll in range(1, max(2, rllpf[i] + 1)):
            phrases.append((i, rll))
            lm.newid(lm.lits.phrase, i, rll)  # definition of f_{i,l}(type-b)
        """

    refs_by_referred = {} #辞書型
    refs_by_referrer = {}
    for i in range(n):
        for j in range(i + 1, n):
            for l in range(2, lpf[j] + 1):
                if i + l <= j and text[i : i + l] == text[j : j + l]:
                    lm.newid(lm.lits.ref, j, i, l)  # definition of ref_{i<-j,l}
                    if not (i, l) in refs_by_referred:
                        refs_by_referred[i, l] = []
                    refs_by_referred[i, l].append(j) #キー[i,l]にjを格納する
                    if not (j, l) in refs_by_referrer:
                        refs_by_referrer[j, l] = []
                    refs_by_referrer[j, l].append(i) #キー[j,l]にiを格納する

    for (i, l) in refs_by_referred.keys(): #キーの個数分,for文をまわす
        lm.newid(lm.lits.referred, i, l) #definition of q_{i,l}

    ###### 新しく追加部分 #######################################
    refs_by_rliterated = {} # 連長圧縮ルールの左のノードが表す区間（キー），右のノードが表す区間の長さ（値）
    refs_by_rlreferrer = {} # 連長圧縮ルールの右のノードが表す区間（キー），左のノードの開始位置（値）
    refs_by_allrule = {} # 連長圧縮ルール全体が表す区間（キー），右のノードの開始位置（値）

    #ref^rの定義
    for i in range(n):
        for j in range(i + 1, n):
            for l in range(2, rllpf[j] + 1):
                # j-i \in PDvi(l)の条件を追加
                if j < i + l  and text[i : i + l] == text[j : j + l] and (l % (j - i)) == 0:
                    lm.newid(lm.lits.rlref, j, i, l)  # definition of {ref^r}_{i<-j,l}
                    if not (i, j + l - i) in refs_by_allrule:
                        refs_by_allrule[i, j + l - i] = []
                    refs_by_allrule[i, j + l - i].append(j)
                    if not (i, j - i) in refs_by_rliterated:
                        refs_by_rliterated[i, j - i] = []
                    refs_by_rliterated[i, j - i].append(l)
                    if not (j, l) in refs_by_rlreferrer:
                        refs_by_rlreferrer[j, l] = []
                    refs_by_rlreferrer[j, l].append(i) # 参照先の位置を格納
                    if not (j,l) in phrases:
                        phrases.append((j, l))
                        # lm.newid(lm.lits.phrase, j, l)  # definition of f_{i,l}（type-B）
                        # print(phrases)

    # print(f"連長圧縮ルール全体 = {refs_by_allrule}")
    # print("連長圧縮左のノード", refs_by_rliterated)
    # print("連帳圧縮右のノード", refs_by_rlreferrer)

    # q'の定義（一旦保留）
    # q'=1ならば,q=1を表すノード, 連長圧縮ルール全体で表されるノード or 連長圧縮ルールの一番左のノードに対応する
    referred_set1 = set(refs_by_rliterated.keys())
    referred_set2 = set(refs_by_allrule.keys())
    referred_set3 = set(refs_by_referred.keys())
    referred_set = (referred_set1|referred_set2|referred_set3)
    refs_by_rlreferred = list(referred_set)
    # print(f"phraseの候補={phrases}")
    # print(f"refの候補={refs_by_referrer}")
    # print(f"ref^rの候補={refs_by_rlreferrer}")
    # print(f"q'の候補={refs_by_rlreferred}")
    for (i, l) in refs_by_rlreferred:
        lm.newid(lm.lits.rlreferred, i, l) # definition of q'_{i<-j,l}

    # refの添え字のリストとref^rの添え字のリストを結合させ重複を除いたリスト
    refs_by_allreferrers = list(set(refs_by_rlreferrer.keys())|set(refs_by_referrer.keys()))

    # // start constraint (2)(3) ###############################
    # (2):phrase(i,l) <=> pstart[i] and pstart[i+l] and \neg{pstart[i+1]} and .. and \neg{pstart[i+l-1]}
    for i in range(n):
        for l in range(1,n - i +1):
            plst = [-lm.getid(lm.lits.pstart, (i + j)) for j in range(1, l)] + [
                lm.getid(lm.lits.pstart, i), #p_iの取得
                lm.getid(lm.lits.pstart, (i + l)), #p_(i+l)の取得
            ]
            lm.newid(lm.lits.phrase, i, l)

        # range_iff_startp:plst全体を表すliteral
        # clauses:条件式(2)の右辺を表す
            range_iff_startp, clauses = pysat_and(lm.newid, plst)
            wcnf.extend(clauses)
            wcnf.extend(pysat_iff(lm.getid(lm.lits.phrase, i, l), range_iff_startp))
        # pysat_iff(x,y)->リスト[[-x,y], [x, -y]]を返す．(x<=>yを表現する関数)

    # (3):there must be at least one new phrase beginning from [i+1,...,i+max(1,lpf[i] or rllpf[i])]
    for i in range(n):
        for l in range(1,n - i + 1):
            if not (i,l) in phrases:
                # print(f"phrasesにないペア={i,l}")
                wcnf.append([-lm.getid(lm.lits.phrase, i, l)])
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
    # // end constraint (2)(3) ###############################

    # // start constraint (4),(5) ###############################
    # (5):if phrase(j,l) = true there must be exactly one i < j such that ref(j,i,l) is true
    for (j, l) in refs_by_allreferrers:
        reflst1 = []
        reflst2 = []
        if (j,l) in refs_by_referrer.keys():
            reflst1 = [lm.getid(lm.lits.ref, j, i, l) for i in refs_by_referrer[j, l]]
        if (j,l) in refs_by_rlreferrer.keys():
            # print(f"reflst(4,5) = {refs_by_rlreferrer[j, l], j, l}")
            reflst2 = [lm.getid(lm.lits.rlref, j, i, l) for i in refs_by_rlreferrer[j, l]]

        reflst = reflst1 + reflst2

        # CardEnc.atmost(literalのリスト,閾値 k) -> "literalのリストの論理和 <= k"を表すリスト
        clauses = CardEnc.atmost(
            reflst,
            bound=1,
            vpool=lm.vpool,
        )
        wcnf.extend(clauses)

        # (4):ref_{・<-j,l}+ref^r{・<-j,l}に対して,iが少なくとも一つが存在する.
        clause = pysat_atleast_one(reflst)

        # var_atleast:条件式(4)の右辺を表すliteral
        # clause_atleast:条件式(4)の右辺を節を表す
        var_atleast, clause_atleast = pysat_name_cnf(lm, [clause]) # この関数じゃなくていいかも？
        wcnf.extend(clause_atleast)
        phrase = lm.getid(lm.lits.phrase, j, l)
        wcnf.extend(pysat_iff(phrase, var_atleast))

    # // end constraint (4),(5) ###############################

    # // start constraint (6) ###############################
    # (6):referred(i,l) = true iff there is some j > i such that ref(j,i,l) = true
    for (i, l) in refs_by_referred.keys():
        assert l > 1
        ref_sources, clauses = pysat_or(
            lm.newid,
            [lm.getid(lm.lits.ref, j, i, l) for j in refs_by_referred[i, l]],
        )
        wcnf.extend(clauses)
        referredid = lm.getid(lm.lits.referred, i, l)
        wcnf.extend(
            pysat_iff(ref_sources, referredid)
        )
    # // end constraint (6) ###############################

    # // start constraint (7) ###############################
    # (7):if (occ,l) is a referred interval, it cannot be a phrase, but pstart[occ] and pstart[occ+l] must be true
    # phrase(occ,l) is only defined if l <= lpf[occ]
    referred = list(refs_by_referred.keys())
    for (occ, l) in referred:
        if l > 1:
            qid = lm.getid(lm.lits.referred, occ, l)
            lst = [-qid] + [lm.getid(lm.lits.pstart, occ + x) for x in range(1, l)]
            wcnf.append(lst)
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, occ)))
            wcnf.append(pysat_if(qid, lm.getid(lm.lits.pstart, occ + l)))
    # // end constraint (7) ###############################

    # // start constraint (8) ###############################
    # (8):区間(j, j + l)が区間(i,j)を繰り返して参照していれば，位置rlreferer[j,l]はフレーズの開始位置となる
    for (j, l) in refs_by_rlreferrer.keys():
        for i in refs_by_rlreferrer[j, l]:
            # print(f"rlref(8) = {refs_by_rlreferrer}")
            wcnf.append(
                pysat_if(
                    lm.getid(lm.lits.rlref, j, i, l),
                    lm.getid(lm.lits.pstart, i)
                )
            )
    # // start constraint (8) ###############################

    # // start constraint (9) ###############################
    # (9):q'の定義
    for (i, l) in refs_by_rlreferred:
        referredlst=[] #q_{i,l}
        rlreflst1=[] # 連長圧縮ルール全体からなるノードのリスト
        rlreflst2=[] # 連長圧縮ルールの左のノードのリスト
        rlreferredlst=[]

        if (i, l) in refs_by_referred:
            referredlst.append(lm.getid(lm.lits.referred, i, l))

        for j in range(n):
            # 連長圧縮ルール全体
            # print(f"i,l,j = {i,l,j}")
            # print(f"allrule = {refs_by_allrule}")
            if (i,l) in refs_by_allrule.keys() and j in refs_by_allrule[i,l]:
                # print(f"rlref_all(9) = {i,j,i + l - j}")
                rlreflst1.append(lm.getid(lm.lits.rlref, j, i, i + l - j))

            # 連長圧縮ルールの左のノード
            if (i, l) in refs_by_rliterated.keys() and j == i + l:
                for rll in refs_by_rliterated[i, l]:
                    # print(f"rlref_left(9) = {i,j,rll}")
                    rlreflst2.append(lm.getid(lm.lits.rlref, j, i, rll))

        rlreferredlst.extend(referredlst + rlreflst1 + rlreflst2)

        clause = pysat_atleast_one(rlreferredlst)
        var_refatleast, clause_refatleast = pysat_name_cnf(lm, [clause])
        wcnf.extend(clause_refatleast)
        rlreferredid = lm.getid(lm.lits.rlreferred, i, l)
        wcnf.extend(pysat_iff(rlreferredid, var_refatleast))
    # // end constraint (9) #################################

    # // start constraint (10) ###############################
    # (10):crossing intervals cannot be referred to at the same time.
    #rlreferred = list(refs_by_rlreferred)
    rlreferred_by_bp = [[] for _ in range(n)] # nサイズのリストを作成
    for (occ, l) in refs_by_rlreferred:
        rlreferred_by_bp[occ].append(l)
    for lst in rlreferred_by_bp:
        lst.sort(reverse=True)

    for (occ1, l1) in refs_by_rlreferred:
        for occ2 in range(occ1 + 1, occ1 + l1):
            for l2 in rlreferred_by_bp[occ2]:
                if l2 == 1:
                    pass
                else:
                    # print(f"l1,l2,occ1,occ2 = {l1,l2,occ1,occ2}")
                    assert l1 > 1 and l2 > 1
                    assert occ1 < occ2 and occ2 < occ1 + l1
                    if occ1 + l1 >= occ2 + l2:
                        break
                    id1 = lm.getid(lm.lits.rlreferred, occ1, l1)
                    id2 = lm.getid(lm.lits.rlreferred, occ2, l2)
                    wcnf.append([-id1, -id2])
    # // end constraint (10) ###############################

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
    return lm, wcnf, phrases, refs_by_referrer, refs_by_rlreferrer

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
def rlslp2str(root, rlslp):
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
                res += rlslp2str(children[0], rlslp)
            else:
                res += rlslp2str(children[0], rlslp)
                res += rlslp2str(children[1], rlslp)
        elif str(ref).startswith("RLrule") == True: # 連帳圧縮ルールの繰り返しを表した葉ノードの場合
            assert len(children) == 2
            # print(f"children_RLrule = {children}")
            for j in range(int((children[1][1] - children[0][0]) / (children[0][1] - children[0][0]))):
                res += rlslp2str(children[0], rlslp)

        else: # 葉ノードの場合
            # print(f"root = {root}")
            # print(f"children_leaves = {children}")
            assert children is None
            # 参照しているノードが連長圧縮全体のノード，SLPルールのノード，文字で場合分けしたい
            if (ref, ref + j - i, None) in rlslp:
                n = (ref, ref + j - i, None)
            else:
                n = (ref, ref + j - i, "RLrule")

            res += rlslp2str(n, rlslp)
    return res

# SLPの解析木の情報を保存
def recover_rlslp(text: bytes, pstartl, refs_by_referrer, refs_by_rlreferrer):
    n = len(text)
    # 各区間に対応するノードの種類を分類
    referred = set((refs_by_referrer[j, l], l) for (j, l) in refs_by_referrer.keys()) # 参照元の位置と長さを保持するタプルを生成

    if len(refs_by_rlreferrer) > 0:
        rlreferred = set((refs_by_rlreferrer[j, l], j, l) for (j, l) in refs_by_rlreferrer.keys())
    else:
        rlreferred = set()

    # ノードが内部ノードかつ蓮長圧縮ルール全体のノードとみなされていた場合，連長圧縮ルール全体のノードとして扱う
    # 繰り返しを表す区間が左に出現していた時発生する

    leaves = [(j, j + l, refs_by_referrer[j, l]) for (j, l) in refs_by_referrer.keys()] + [(j, j + l, refs_by_rlreferrer[j, l]) for (j, l) in refs_by_rlreferrer.keys()] # 葉ノードが表す区間
    for i in range(len(pstartl) - 1):
        if pstartl[i + 1] - pstartl[i] == 1: # pstartl[i]が長さ1のファクタの開始位置の場合
            leaves.append((pstartl[i], pstartl[i + 1], text[pstartl[i]]))

    internal = [(occ, occ + l, None) for (occ, l) in referred] # 内部ノードが表す区間(SLP)
    rlinternal = [(occ, j + l , "RLrule") for (occ, j, l) in rlreferred] # 連長圧縮全体を表す内部ノードの区間(RLSLP)
            # leaves = [(occ, j + l - i, None)]
            # print(f"occ, j, l = {occ, j, l}")
    for (i, l) in referred:
        for (j, rl) in refs_by_rlreferrer.keys():
            if i == refs_by_rlreferrer[j, rl] and i + l == j + rl:
                # print(f"i, l, j, rl={i,l,j,rl}")
                internal.remove((i, i + l, None))

    # print(f"referred = {referred}")
    # print(f"rlreferred = {rlreferred}")
    # rint(f"internal = {internal}")
    # print(f"rlinternal = {rlinternal}")
    # print(f"leaves = {leaves}")
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
def smallest_RLSLP(text: bytes, exp: Optional[SLPExp] = None) -> SLPType:
    """
    Compute the smallest SLP.
    """
    total_start = time.time()
    lm, wcnf, phrases, refs_by_referrer, refs_by_rlreferrer = smallest_RLSLP_WCNF(text) # 条件式を生成
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
    # MAX-SATの解からRLSLPを生成
    root, rlslp = recover_rlslp(text, posl, refs, rlrefs)
    # print(f"root={root}, rlslp = {rlslp}, rlslpkeys={rlslp.keys()}")

    rlslpsize = len(posl) - 2 + len(set(text))

    if exp:
        exp.time_total = time.time() - total_start
        exp.time_prep = time_prep
        exp.factors = f"{(root, rlslp)}"
        exp.factor_size = rlslpsize  # len(internal_nodes) + len(set(text))
        exp.fill(wcnf)

    check = bytes(rlslp2str(root, rlslp))

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
    #print("start!")
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

    rlslp = smallest_RLSLP(text, exp) # SLPの最小サイズを計算

    if args.output == "":
        print(exp.to_json(ensure_ascii=False))  # type: ignore
    else:
        with open(args.output, "w") as f:
            json.dump(exp, f, ensure_ascii=False)
