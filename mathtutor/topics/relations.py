"""Тема: свойства бинарных отношений на конечном множестве."""
from __future__ import annotations

import re
from itertools import product

from .base import AnswerFormatError, Malrule, Task, Topic

PROPS = ["refl", "sym", "antisym", "trans"]
PROP_NAME = {"refl": "рефлексивность", "sym": "симметричность",
             "antisym": "антисимметричность", "trans": "транзитивность"}


def is_reflexive(a, r):
    return all((x, x) in r for x in a)


def is_symmetric(a, r):
    return all((y, x) in r for x, y in r)


def is_antisymmetric(a, r):
    return all(not ((y, x) in r and x != y) for x, y in r)


def is_transitive(a, r):
    return all((x, z) in r for x, y in r for y2, z in r if y == y2)


def properties(a, r) -> frozenset:
    checks = {"refl": is_reflexive, "sym": is_symmetric, "antisym": is_antisymmetric, "trans": is_transitive}
    return frozenset(p for p in PROPS if checks[p](a, r))


def witness(prop: str, a, r) -> str | None:
    """Контрпример к свойству или None, если свойство выполняется."""
    pairs = sorted(r)
    if prop == "refl":
        for x in a:
            if (x, x) not in r:
                return f"в отношении нет пары ({x}, {x})"
    elif prop == "sym":
        for x, y in pairs:
            if (y, x) not in r:
                return f"есть пара ({x}, {y}), но нет пары ({y}, {x})"
    elif prop == "antisym":
        for x, y in pairs:
            if x != y and (y, x) in r:
                return f"есть обе пары ({x}, {y}) и ({y}, {x}) при {x} ≠ {y}"
    else:
        for x, y in pairs:
            for y2, z in pairs:
                if y == y2 and (x, z) not in r:
                    return f"есть пары ({x}, {y}) и ({y}, {z}), но нет пары ({x}, {z})"
    return None


def relation_text(a, r) -> str:
    return (f"A = {{{', '.join(map(str, a))}}}, "
            f"R = {{{', '.join(f'({x}, {y})' for x, y in sorted(r))}}}")


class RelationsTopic(Topic):
    id = "rel"
    title = "Свойства бинарных отношений"
    malrule_titles = {
        "antisym_is_not_sym": "антисимметричность принята за «не симметричность»",
        "reflexive_if_any_loop": "рефлексивность признана при наличии хотя бы одной пары (a, a)",
        "transitive_distinct_only": "транзитивность проверена только для различных a, b, c",
    }

    # --------------------------------------------------------------- создание
    def generate(self, rng, d):
        m = 3 if d == 1 else 4
        a = list(range(1, m + 1))
        family = rng.choice(["equiv", "leq", "div", "random", "random"])
        if family == "equiv":
            blocks = [rng.randrange(1 + m // 2) for _ in a]
            r = {(x, y) for x in a for y in a if blocks[x - 1] == blocks[y - 1]}
        elif family == "leq":
            r = {(x, y) for x in a for y in a if x <= y}
        elif family == "div":
            r = {(x, y) for x in a for y in a if y % x == 0}
        else:
            r = {p for p in product(a, repeat=2) if rng.random() < 0.4}
        if rng.random() < 0.6 or not r:  # возмущение: ломаем одно свойство
            pair = (rng.choice(a), rng.choice(a))
            r = r ^ {pair}
        if not r:
            r = {(a[0], a[1])}
        ans = properties(a, r)
        statement = (f"Дано множество и отношение на нём: {relation_text(a, r)}.\n"
                     "Какие свойства выполняются? Введите номера через пробел: "
                     "1 — рефлексивность, 2 — симметричность, 3 — антисимметричность, "
                     "4 — транзитивность. Если не выполняется ни одно, введите 0.")
        return statement, {"A": a, "R": sorted(r)}, ans

    # ------------------------------------------------------------------ ответ
    @staticmethod
    def _token(tok: str) -> str | None:
        t = tok.lower()
        if t in "1234" and len(t) == 1:
            return PROPS[int(t) - 1]
        for prefix, prop in (("реф", "refl"), ("сим", "sym"), ("анти", "antisym"), ("тран", "trans")):
            if t.startswith(prefix):
                return prop
        return None

    def parse(self, task, raw):
        s = raw.strip().lower()
        if s in ("0", "-", "нет", "ничего", "ни одно"):
            return frozenset()
        tokens = [t for t in re.split(r"[,;\s]+", s) if t]
        if not tokens:
            raise AnswerFormatError("Введите номера свойств (1–4) через пробел или 0, если нет ни одного.")
        result = set()
        for tok in tokens:
            prop = self._token(tok)
            if prop is None:
                raise AnswerFormatError(f"Не понял «{tok}». Используйте номера 1–4 (или 0, если ни одно не выполняется).")
            result.add(prop)
        return frozenset(result)

    def show(self, value):
        return " ".join(str(PROPS.index(p) + 1) for p in PROPS if p in value) or "0"

    def describe(self, value):
        if not value:
            return "0 (ни одно свойство не выполняется)"
        names = ", ".join(PROP_NAME[p] for p in PROPS if p in value)
        return f"{self.show(value)} ({names})"

    # ------------------------------------------------------------ диагностика
    def malrules(self, task: Task) -> list[Malrule]:
        a, r = task.data["A"], set(map(tuple, task.data["R"]))
        truth = set(task.answer)
        out = []

        c = set(truth) - {"antisym"}
        if "sym" not in truth:
            c.add("antisym")
        out.append(Malrule("antisym_is_not_sym", "антисимметричность — это не «отсутствие симметричности»: "
                           "из (a, b) и (b, a) должно следовать a = b", frozenset(c)))

        c = set(truth) - {"refl"}
        if any((x, x) in r for x in a):
            c.add("refl")
        out.append(Malrule("reflexive_if_any_loop", "рефлексивность требует пары (a, a) для КАЖДОГО "
                           "элемента множества, а не для некоторых", frozenset(c)))

        distinct_ok = all((x, z) in r for x, y in r for y2, z in r
                          if y == y2 and len({x, y, z}) == 3)
        c = set(truth) - {"trans"}
        if distinct_ok:
            c.add("trans")
        out.append(Malrule("transitive_distinct_only", "в проверке транзитивности нужно рассматривать и случаи, "
                           "когда элементы совпадают: из (a, b), (b, a) следует (a, a)", frozenset(c)))
        return [m for m in out if m.value != task.answer]

    def explain_wrong(self, task, value):
        a, r = task.data["A"], set(map(tuple, task.data["R"]))
        truth = set(task.answer)
        lines = []
        for p in PROPS:
            claimed = p in value
            if claimed == (p in truth):
                continue
            name = PROP_NAME[p]
            if claimed:
                lines.append(f"{name.capitalize()}: вы считаете, что она выполняется, но это не так: "
                             f"{witness(p, a, r)}.")
            else:
                lines.append(f"{name.capitalize()}: вы считаете, что она не выполняется, но контрпримера нет, "
                             f"свойство выполняется. Перепроверьте определение.")
        return lines

    def hints(self, task):
        a, r = task.data["A"], set(map(tuple, task.data["R"]))
        truth = task.answer
        first = "выполняется" if "refl" in truth else "не выполняется"
        return [
            "Выпишите определения четырёх свойств и проверяйте каждое отдельно.",
            "Для каждого свойства ищите контрпример: свойство выполняется, только если контрпримера нет.",
            f"Начните с рефлексивности: она {first}.",
        ]

    def solution(self, task):
        a, r = task.data["A"], set(map(tuple, task.data["R"]))
        lines = []
        for p in PROPS:
            w = witness(p, a, r)
            lines.append(f"{PROP_NAME[p].capitalize()}: " + ("выполняется." if w is None else f"не выполняется ({w})."))
        return lines
