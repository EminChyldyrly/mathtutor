"""Bayesian Knowledge Tracing: вероятностная оценка того, что тема освоена.

Модель с четырьмя параметрами (Corbett & Anderson, 1995):
  p_init  — вероятность того, что тема уже была освоена до начала,
  p_learn — вероятность освоить тему после очередной попытки,
  p_slip  — вероятность ошибиться, зная тему,
  p_guess — вероятность угадать, не зная темы.
Параметры ниже выбраны разумными по умолчанию, а не обучены на данных.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.2
    p_learn: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.2


def update(p_known: float, correct: bool, params: BKTParams = BKTParams()) -> float:
    """Новая оценка освоения после одной наблюдаемой попытки."""
    if correct:
        evidence = p_known * (1 - params.p_slip) + (1 - p_known) * params.p_guess
        posterior = p_known * (1 - params.p_slip) / evidence
    else:
        evidence = p_known * params.p_slip + (1 - p_known) * (1 - params.p_guess)
        posterior = p_known * params.p_slip / evidence
    return posterior + (1 - posterior) * params.p_learn


def difficulty_for(mastery: float) -> int:
    """Уровень сложности следующей задачи по оценке освоения."""
    if mastery < 0.4:
        return 1
    if mastery < 0.75:
        return 2
    return 3
