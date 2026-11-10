"""Тема: определитель матрицы 2×2 и 3×3."""
from __future__ import annotations

from fractions import Fraction

from .base import Malrule, Task, Topic, fmt_frac, paren, parse_number


def det2(m):
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def sarrus_parts(m):
    """(сумма «положительных» произведений, сумма «отрицательных»)."""
    pos = m[0][0] * m[1][1] * m[2][2] + m[0][1] * m[1][2] * m[2][0] + m[0][2] * m[1][0] * m[2][1]
    neg = m[0][2] * m[1][1] * m[2][0] + m[0][0] * m[1][2] * m[2][1] + m[0][1] * m[1][0] * m[2][2]
    return pos, neg


def det3(m):
    pos, neg = sarrus_parts(m)
    return pos - neg


def determinant(m):
    return det2(m) if len(m) == 2 else det3(m)


def _minors_first_row(m):
    return [det2([[m[1][1], m[1][2]], [m[2][1], m[2][2]]]),
            det2([[m[1][0], m[1][2]], [m[2][0], m[2][2]]]),
            det2([[m[1][0], m[1][1]], [m[2][0], m[2][1]]])]


def matrix_text(m) -> str:
    cells = [[str(x) for x in row] for row in m]
    w = max(len(c) for row in cells for c in row)
    return "\n".join("[ " + "  ".join(c.rjust(w) for c in row) + " ]" for row in cells)


class DeterminantTopic(Topic):
    id = "det"
    title = "Определитель матрицы"
    malrule_titles = {
        "det_sign": "перепутан знак результата",
        "main_diagonal_only": "учтена только главная диагональ",
        "det_plus_between": "произведения диагоналей сложены, а не вычтены",
        "sarrus_all_plus": "все слагаемые правила Саррюса взяты со знаком «+»",
        "laplace_no_signs": "в разложении по строке не чередуются знаки",
    }

    def generate(self, rng, d):
        n = 2 if d == 1 else 3
        lo, hi = {1: (-5, 9), 2: (-4, 6), 3: (-9, 9)}[d]
        while True:
            m = [[rng.randint(lo, hi) for _ in range(n)] for _ in range(n)]
            if determinant(m) != 0:
                break
        statement = "Вычислите определитель матрицы:\n" + matrix_text(m)
        return statement, {"matrix": m}, Fraction(determinant(m))

    def parse(self, task, raw):
        return parse_number(raw)

    def show(self, value):
        return fmt_frac(value)

    def malrules(self, task: Task) -> list[Malrule]:
        m = task.data["matrix"]
        ans = task.answer
        out = [Malrule("det_sign", "знак результата противоположный; проверьте порядок вычитания "
                                   "(главная диагональ минус побочная, а не наоборот)", -ans)]
        if len(m) == 2:
            out.append(Malrule("main_diagonal_only", "вы взяли только произведение главной диагонали "
                                                     "и забыли вычесть произведение побочной",
                               Fraction(m[0][0] * m[1][1])))
            out.append(Malrule("det_plus_between", "между произведениями диагоналей нужен минус, "
                                                   "а вы их сложили", Fraction(m[0][0] * m[1][1] + m[0][1] * m[1][0])))
        else:
            pos, neg = sarrus_parts(m)
            out.append(Malrule("sarrus_all_plus", "в правиле Саррюса три произведения идут со знаком «−», "
                                                  "а вы взяли все шесть со знаком «+»", Fraction(pos + neg)))
            a, b, c = _minors_first_row(m)
            out.append(Malrule("laplace_no_signs", "при разложении по строке знаки должны чередоваться "
                                                   "(+ − +), а вы их не меняли",
                               Fraction(m[0][0] * a + m[0][1] * b + m[0][2] * c)))
            out.append(Malrule("main_diagonal_only", "вы перемножили только главную диагональ, "
                                                     "остальные слагаемые потеряны",
                               Fraction(m[0][0] * m[1][1] * m[2][2])))
        return [r for r in out if r.value != ans]

    def hints(self, task):
        m = task.data["matrix"]
        if len(m) == 2:
            (a, b), (c, d) = m
            return [
                "Для матрицы 2×2 определитель равен разности произведений диагоналей: "
                "главная минус побочная.",
                f"Главная диагональ: {paren(a)}·{paren(d)}, побочная: {paren(b)}·{paren(c)}. "
                f"Значит, det = {paren(a)}·{paren(d)} − {paren(b)}·{paren(c)}.",
                f"Произведения равны {a * d} и {b * c}. Осталось вычесть второе из первого.",
            ]
        pos, neg = sarrus_parts(m)
        return [
            "Для матрицы 3×3 используйте правило Саррюса или разложение по строке "
            "со знаками «шахматной доски» (+ − +).",
            "Правило Саррюса: три «положительных» произведения (главная диагональ и два «треугольника» "
            "рядом с ней) и три «отрицательных» (побочная диагональ и два её «треугольника»).",
            f"Сумма «положительных» произведений равна {pos}, сумма «отрицательных» равна {neg}. "
            "Осталось вычесть.",
        ]

    def solution(self, task):
        m = task.data["matrix"]
        if len(m) == 2:
            (a, b), (c, d) = m
            return [f"det = {paren(a)}·{paren(d)} − {paren(b)}·{paren(c)} = {a * d} − {paren(b * c)} "
                    f"= {fmt_frac(task.answer)}"]
        pos, neg = sarrus_parts(m)
        return [f"По правилу Саррюса: «положительные» произведения дают {pos}, «отрицательные» дают {neg}.",
                f"det = {pos} − {paren(neg)} = {fmt_frac(task.answer)}"]
