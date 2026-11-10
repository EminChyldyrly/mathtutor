"""Тема: комбинаторика (сочетания, размещения, повторения, перестановки букв)."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from math import comb, factorial, perm, prod

from .base import Malrule, Task, Topic, fmt_frac, parse_number

# слова с повторяющимися буквами
WORDS = ["АННА", "ШАШКА", "ПАПА", "ТОТО", "ЛОЖКА", "КОЛОКОЛ", "МАТЕМАТИКА", "ПОПУГАЙ"]


def multiset_count(word: str) -> int:
    return factorial(len(word)) // prod(factorial(c) for c in Counter(word).values())


def kind_answer(kind: str, n: int, k: int, word: str | None = None) -> int:
    if kind == "C":
        return comb(n, k)
    if kind == "A":
        return perm(n, k)
    if kind == "rep_arr":
        return n ** k
    if kind == "rep_comb":
        return comb(n + k - 1, k)
    if kind == "multiset":
        return multiset_count(word)
    raise ValueError(kind)


def statement_for(kind: str, n: int, k: int, word: str | None) -> str:
    if kind == "C":
        return (f"Из {n} кандидатов нужно выбрать комиссию из {k} человек. "
                f"Порядок в комиссии не важен. Сколько существует способов?")
    if kind == "A":
        return (f"В конкурсе участвуют {n} человек. Сколькими способами можно распределить "
                f"призовые места с 1-го по {k}-е (все призёры разные)?")
    if kind == "rep_arr":
        return (f"Сколько существует {k}-значных кодов, составленных из {n} различных символов, "
                f"если символы в коде могут повторяться?")
    if kind == "rep_comb":
        return (f"В кондитерской продаются {n} видов пирожных. Сколькими способами можно купить {k} пирожных, "
                f"если порядок покупки не важен, а пирожные одного вида неразличимы "
                f"(видов можно брать несколько штук)?")
    return f"Сколько различных «слов» (в том числе бессмысленных) можно получить, переставляя буквы слова «{word}»?"


class CombinatoricsTopic(Topic):
    id = "comb"
    title = "Комбинаторика"
    malrule_titles = {
        "order_counted": "учтён порядок, хотя он не важен",
        "order_ignored": "порядок не учтён, хотя он важен",
        "repeats_allowed": "разрешены повторы, хотя элементы не повторяются",
        "repeats_forbidden": "повторы запрещены, хотя они допустимы",
        "ignored_repeated_letters": "не учтено, что одинаковые буквы неразличимы",
        "stars_off_by_one": "ошибка в формуле сочетаний с повторениями (n + k − 1)",
    }

    def generate(self, rng, d):
        kinds = {1: ["C", "A"], 2: ["C", "A", "rep_arr", "multiset"], 3: ["rep_comb", "multiset", "rep_arr", "A"]}[d]
        kind = rng.choice(kinds)
        word = None
        if kind == "multiset":
            pool = [w for w in WORDS if (len(w) <= 7 if d < 3 else True)]
            word = rng.choice(pool)
            n, k = len(word), 0
        elif kind == "rep_arr":
            n, k = rng.randint(3, 9), rng.randint(3, 5)
        elif kind == "rep_comb":
            n, k = rng.randint(3, 6), rng.randint(2, 5)
        else:
            n = rng.randint(5, 10)
            k = rng.randint(2, min(4, n - 1))
        data = {"kind": kind, "n": n, "k": k, "word": word}
        return statement_for(kind, n, k, word), data, Fraction(kind_answer(kind, n, k, word))

    def parse(self, task, raw):
        return parse_number(raw)

    def show(self, value):
        return fmt_frac(value)

    def malrules(self, task: Task) -> list[Malrule]:
        kind, n, k, word = (task.data[x] for x in ("kind", "n", "k", "word"))
        ans = task.answer
        cands: list[tuple[str, str, int]] = []
        if kind == "C":
            cands += [("order_counted", "вы посчитали размещения (порядок учтён), а нужны сочетания: "
                                         "комиссия из тех же людей в другом порядке — та же комиссия", perm(n, k)),
                      ("repeats_allowed", "вы разрешили повторы (n^k), но один человек не может войти "
                                          "в комиссию дважды", n ** k)]
        elif kind == "A":
            cands += [("order_ignored", "вы посчитали сочетания, но порядок важен: призовые места разные", comb(n, k)),
                      ("repeats_allowed", "вы разрешили повторы (n^k), но один участник не может занять два места",
                       n ** k)]
        elif kind == "rep_arr":
            cands += [("order_ignored", "в коде порядок символов важен, а сочетания его не учитывают", comb(n, k) if k <= n else None),
                      ("repeats_forbidden", "вы запретили повторы (размещения), а в условии они допустимы",
                       perm(n, k) if k <= n else None)]
        elif kind == "multiset":
            cands += [("ignored_repeated_letters", "вы посчитали n!, как будто все буквы разные; "
                                                    "одинаковые буквы нужно делить на k! каждую", factorial(n))]
        else:  # rep_comb
            cands += [("repeats_forbidden", "вы запретили повторы (C(n, k)), а виды можно брать несколько раз",
                       comb(n, k) if k <= n else None),
                      ("order_counted", "вы посчитали n^k, то есть учли порядок покупки, а он не важен", n ** k),
                      ("stars_off_by_one", "в формуле сочетаний с повторениями нужно C(n + k − 1, k)", comb(n + k, k))]
        return [Malrule(i, e, Fraction(v)) for i, e, v in cands if v is not None and Fraction(v) != ans]

    def hints(self, task):
        kind, n, k, word = (task.data[x] for x in ("kind", "n", "k", "word"))
        q = "Ответьте на два вопроса: важен ли порядок элементов и могут ли элементы повторяться?"
        if kind == "C":
            return [q, "Порядок не важен и повторов нет: это сочетания C(n, k) = n! / (k!·(n − k)!).",
                    f"Подставьте: C({n}, {k}) = {n}! / ({k}!·{n - k}!)."]
        if kind == "A":
            return [q, "Порядок важен и повторов нет: это размещения A(n, k) = n! / (n − k)!.",
                    f"Подставьте: A({n}, {k}) = {n}! / {n - k}! = {' · '.join(str(n - i) for i in range(k))}."]
        if kind == "rep_arr":
            return [q, "Порядок важен и повторы разрешены: на каждую из k позиций есть n вариантов.",
                    f"Значит, ответ — произведение из {k} одинаковых множителей: {n}^{k}."]
        if kind == "rep_comb":
            return [q, "Порядок не важен, повторы разрешены: сочетания с повторениями C(n + k − 1, k).",
                    f"Подставьте: C({n} + {k} − 1, {k}) = C({n + k - 1}, {k})."]
        counts = sorted(Counter(word).values(), reverse=True)
        denom = "·".join(f"{c}!" for c in counts if c > 1)
        return [q, "Буквы переставляются, но одинаковые буквы неразличимы: "
                   "перестановки с повторениями n! / (k₁!·k₂!·…).",
                f"В слове «{word}» {n} букв; одинаковые встречаются {', '.join(str(c) for c in counts if c > 1)} раз(а). "
                f"Ответ: {n}! / ({denom})."]

    def solution(self, task):
        kind, n, k, word = (task.data[x] for x in ("kind", "n", "k", "word"))
        name = {"C": f"C({n}, {k})", "A": f"A({n}, {k})", "rep_arr": f"{n}^{k}",
                "rep_comb": f"C({n + k - 1}, {k})", "multiset": f"перестановки букв «{word}»"}[kind]
        return [f"{name} = {fmt_frac(task.answer)}"]
