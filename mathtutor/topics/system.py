"""Тема: системы линейных уравнений с единственным решением."""
from __future__ import annotations

import re
from fractions import Fraction

from .base import AnswerFormatError, Malrule, Task, Topic, fmt_frac, parse_number

NAMES = ["x", "y", "z"]


def det_fraction(a):
    """Определитель квадратной матрицы 2×2 или 3×3 (для проверки невырожденности)."""
    if len(a) == 2:
        return a[0][0] * a[1][1] - a[0][1] * a[1][0]
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def equation_text(row, rhs, names) -> str:
    parts = []
    for coef, name in zip(row, names):
        if coef == 0:
            continue
        mag = abs(coef)
        body = name if mag == 1 else f"{mag}{name}"
        if not parts:
            parts.append(body if coef > 0 else f"−{body}")
        else:
            parts.append(f"{'+' if coef > 0 else '−'} {body}")
    return f"{' '.join(parts)} = {rhs}".replace("= -", "= −")


class SystemTopic(Topic):
    id = "system"
    title = "Системы линейных уравнений"
    malrule_titles = {
        "swapped_values": "значения неизвестных перепутаны местами",
        "sign_error": "ошибка в знаке одного из неизвестных",
    }

    def generate(self, rng, d):
        n = 2 if d == 1 else 3
        lo, hi = {1: (-4, 5), 2: (-3, 4), 3: (-7, 8)}[d]
        names = NAMES[:n]
        while True:
            a = [[rng.randint(lo, hi) for _ in range(n)] for _ in range(n)]
            if det_fraction(a) != 0:
                break
        sol = [rng.randint(-5, 5) for _ in range(n)]
        b = [sum(c * s for c, s in zip(row, sol)) for row in a]
        eqs = "\n".join(equation_text(row, rhs, names) for row, rhs in zip(a, b))
        statement = (f"Решите систему уравнений:\n{eqs}\n"
                     f"Ответ запишите как {', '.join(names)} (например: {', '.join(['1'] * n)}).")
        return statement, {"A": a, "b": b, "names": names}, tuple(Fraction(s) for s in sol)

    def parse(self, task, raw):
        names = task.data["names"]
        n = len(names)
        s = raw.strip().replace("−", "-")
        named = re.findall(r"([A-Za-z])\s*=\s*(-?\s*\d+(?:[./]\d+)?)", s)
        if named:
            got = {}
            for name, val in named:
                if name in got:
                    raise AnswerFormatError(f"Неизвестное {name} указано дважды.")
                got[name] = parse_number(val.replace(" ", ""))
            if set(got) != set(names):
                raise AnswerFormatError(f"Нужны значения для {', '.join(names)}.")
            return tuple(got[nm] for nm in names)
        s = s.strip("()[]{}")
        tokens = [t for t in re.split(r"[,;\s]+", s) if t]
        if len(tokens) != n:
            raise AnswerFormatError(f"Введите {n} числа(-ел) через пробел или запятую: {', '.join(names)}.")
        return tuple(parse_number(t) for t in tokens)

    def show(self, value):
        return "(" + ", ".join(fmt_frac(v) for v in value) + ")"

    def malrules(self, task: Task) -> list[Malrule]:
        names = task.data["names"]
        sol = task.answer
        out: list[Malrule] = []
        for i in range(len(sol)):
            for j in range(i + 1, len(sol)):
                if sol[i] != sol[j]:
                    swapped = list(sol)
                    swapped[i], swapped[j] = swapped[j], swapped[i]
                    out.append(Malrule("swapped_values", f"значения {names[i]} и {names[j]} перепутаны местами",
                                       tuple(swapped)))
        for i, v in enumerate(sol):
            if v != 0:
                neg = list(sol)
                neg[i] = -v
                out.append(Malrule("sign_error", f"у неизвестной {names[i]} потерян или добавлен знак минус",
                                   tuple(neg)))
        return out

    def explain_wrong(self, task, value):
        a, b = task.data["A"], task.data["b"]
        names = task.data["names"]
        lines = []
        for k, (row, rhs) in enumerate(zip(a, b), start=1):
            left = sum(c * v for c, v in zip(row, value))
            if left != rhs:
                lines.append(f"Подстановка в уравнение {k} ({equation_text(row, rhs, names)}) даёт "
                             f"{fmt_frac(left).replace('-', '−')} вместо {str(rhs).replace('-', '−')}, "
                             f"так что уравнение не выполняется.")
        if lines:
            lines.insert(0, "Проверка подстановкой:")
        return lines

    def hints(self, task):
        a, names = task.data["A"], task.data["names"]
        sol = task.answer
        pivot = next((i for i, row in enumerate(a) if row[0] != 0), 0)
        other = next((r for r in range(len(a)) if r != pivot and a[r][0] != 0), None)
        if other is None:
            step = f"Неизвестная {names[0]} уже отсутствует в остальных уравнениях, переходите к следующей."
        else:
            k = Fraction(a[other][0], a[pivot][0])
            step = (f"Чтобы исключить {names[0]} из уравнения {other + 1}, вычтите из него уравнение "
                    f"{pivot + 1}, умноженное на {fmt_frac(k)}.")
        return [
            "Решайте методом Гаусса: исключайте неизвестные по очереди, пока не останется уравнение "
            "с одной неизвестной. Затем подставляйте найденное обратно.",
            step,
            f"Ответ для последней неизвестной: {names[-1]} = {fmt_frac(sol[-1])}. "
            "Найдите остальные и проверьте подстановкой во все уравнения.",
        ]

    def solution(self, task):
        names, sol = task.data["names"], task.answer
        return ["Метод Гаусса (или подстановка) приводит к решению: "
                + ", ".join(f"{nm} = {fmt_frac(v)}" for nm, v in zip(names, sol)) + ".",
                "Проверка: подстановка этих значений обращает каждое уравнение в верное равенство."]
