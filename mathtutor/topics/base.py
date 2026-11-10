"""Базовые типы тем: задача, «типичная ошибка», разбор ответа."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from fractions import Fraction


class AnswerFormatError(ValueError):
    """Ответ нельзя разобрать. Это не неверный ответ: попытка не засчитывается."""


@dataclass(frozen=True)
class Malrule:
    """Типичная ошибка: какой ответ получится, если ученик применил неверное правило."""

    id: str
    explanation: str
    value: object


@dataclass
class Task:
    topic_id: str
    difficulty: int
    seed: int
    statement: str
    data: dict
    answer: object


def fmt_frac(x: Fraction) -> str:
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def paren(x: int | Fraction) -> str:
    """Число для подстановки в формулу: отрицательные берём в скобки."""
    return f"({fmt_frac(x)})" if x < 0 else fmt_frac(x)


_NUMBER = re.compile(r"[+-]?\d+(?:[.,]\d+)?|[+-]?\d+/\d+")


def parse_number(raw: str) -> Fraction:
    """'5', '-3', '1/2', '0.5', '0,5' -> Fraction. Иначе AnswerFormatError."""
    s = raw.strip().replace("−", "-")
    if not _NUMBER.fullmatch(s):
        raise AnswerFormatError("Введите одно число, например 12, -3 или 1/2.")
    try:
        return Fraction(s.replace(",", "."))
    except ZeroDivisionError:
        raise AnswerFormatError("Знаменатель дроби не может быть равен нулю.") from None


class Topic:
    """Тема: умеет создавать задачу по (сложность, seed), разбирать ответ и
    перечислять типичные ошибки."""

    id = ""
    title = ""
    malrule_titles: dict[str, str] = {}

    # ---- создание
    def generate(self, rng: random.Random, difficulty: int) -> tuple[str, dict, object]:
        raise NotImplementedError

    def make(self, difficulty: int, seed: int) -> Task:
        if difficulty not in (1, 2, 3):
            raise ValueError("сложность: 1, 2 или 3")
        # строковый seed детерминирован и не зависит от PYTHONHASHSEED
        rng = random.Random(f"{self.id}:{difficulty}:{seed}")
        statement, data, answer = self.generate(rng, difficulty)
        return Task(self.id, difficulty, seed, statement, data, answer)

    # ---- ответ
    def parse(self, task: Task, raw: str) -> object:
        raise NotImplementedError

    def equal(self, a: object, b: object) -> bool:
        return a == b

    def show(self, value: object) -> str:
        """Форма ответа, которую принимает parse (нужна для круговой проверки)."""
        return str(value)

    def describe(self, value: object) -> str:
        """Форма ответа для показа ученику; по умолчанию совпадает с show."""
        return self.show(value)

    # ---- диагностика и помощь
    def malrules(self, task: Task) -> list[Malrule]:
        return []

    def explain_wrong(self, task: Task, value: object) -> list[str]:
        return []

    def hints(self, task: Task) -> list[str]:
        return []

    def solution(self, task: Task) -> list[str]:
        return []
