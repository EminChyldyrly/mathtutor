"""Логика репетитора: проверка ответа с диагностикой, выбор задач, сеанс, отчёт."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Iterator

from . import bkt
from .profile import Profile
from .topics import MALRULE_TITLES, TOPICS, AnswerFormatError, Task, make_task

MAX_ATTEMPTS = 3


@dataclass
class Feedback:
    verdict: str                      # 'correct' | 'wrong' | 'format'
    messages: list[str]
    error_ids: list[str] = field(default_factory=list)

    @property
    def correct(self) -> bool:
        return self.verdict == "correct"


def evaluate(task: Task, raw: str) -> Feedback:
    """Проверяет ответ. Ответ неверен, только если он разобран и не совпал;
    нечитаемый ввод — отдельный вердикт 'format' (попытка не тратится)."""
    topic = TOPICS[task.topic_id]
    try:
        value = topic.parse(task, raw)
    except AnswerFormatError as exc:
        return Feedback("format", [str(exc)])
    if topic.equal(value, task.answer):
        return Feedback("correct", ["Верно!"])

    messages = ["Неверно."]
    error_ids: list[str] = []
    for rule in topic.malrules(task):
        if topic.equal(value, rule.value):
            messages.append(f"Похоже на типичную ошибку: {rule.explanation}.")
            if rule.id not in error_ids:
                error_ids.append(rule.id)
    messages.extend(topic.explain_wrong(task, value))
    return Feedback("wrong", messages, error_ids)


# ---------------------------------------------------------------- выбор задачи

def choose_topic(profile: Profile, rng: random.Random, last_topics: list[str]) -> str:
    """Тема с наименьшим освоением; одну тему не даём трижды подряд."""
    ids = list(TOPICS)
    banned = {last_topics[-1]} if len(last_topics) >= 2 and last_topics[-1] == last_topics[-2] else set()
    pool = [t for t in ids if t not in banned] or ids
    lowest = min(profile.topics[t].mastery for t in pool)
    return rng.choice([t for t in pool if profile.topics[t].mastery <= lowest + 0.05])


def next_task(profile: Profile, rng: random.Random, last_topics: list[str]) -> Task:
    tid = choose_topic(profile, rng, last_topics)
    difficulty = bkt.difficulty_for(profile.topics[tid].mastery)
    return make_task(tid, difficulty, rng.randrange(10 ** 9))


# ------------------------------------------------------------------------ сеанс

def run_practice(profile: Profile, n: int, rng: random.Random,
                 input_fn: Callable[[str], str] = input, out: Callable[[str], None] = print,
                 task_source: Iterator[Task] | None = None) -> int:
    """Интерактивный сеанс. Возвращает число завершённых задач.
    Команды: h — подсказка, s — показать решение, q — выйти."""
    done = 0
    last: list[str] = []
    out("Команды: h — подсказка, s — показать решение, q — выйти. Ответы пишите обычным текстом.\n")
    for i in range(1, n + 1):
        task = next(task_source, None) if task_source is not None else next_task(profile, rng, last)
        if task is None:
            break
        topic = TOPICS[task.topic_id]
        stats = profile.topics[task.topic_id]
        out(f"Задача {i}/{n}  [{topic.title}, сложность {task.difficulty}, "
            f"освоение {stats.mastery:.0%}]")
        out(task.statement)

        hints_shown, attempts, solved, gave_up = 0, 0, False, False
        error_ids: list[str] = []
        hints = topic.hints(task)
        while True:
            try:
                raw = input_fn("> ").strip()
            except EOFError:
                raw = "q"
            cmd = raw.lower()
            if cmd == "q":
                if attempts or hints_shown:  # начатую задачу засчитываем как неудачную
                    profile.record(task.topic_id, task.difficulty, task.seed, False,
                                   hints_shown, error_ids, max(attempts, 1))
                    done += 1
                out("Сеанс завершён.")
                return done
            if cmd == "h":
                if hints_shown < len(hints):
                    out(f"Подсказка {hints_shown + 1}/{len(hints)}: {hints[hints_shown]}")
                    hints_shown += 1
                else:
                    out("Подсказки закончились. Введите ответ или s, чтобы увидеть решение.")
                continue
            if cmd == "s":
                gave_up = True
                break
            fb = evaluate(task, raw)
            if fb.verdict == "format":
                out(fb.messages[0])
                continue
            attempts += 1
            if fb.correct:
                solved = True
                out("Верно!" + ("" if attempts == 1 and not hints_shown else
                                " Решено не с первой попытки или с подсказкой, "
                                "поэтому в оценку освоения это пойдёт как неуверенный результат."))
                break
            out("\n".join(fb.messages))
            for eid in fb.error_ids:
                error_ids.append(eid)
            if attempts >= MAX_ATTEMPTS:
                gave_up = True
                out(f"Попытки закончились. Правильный ответ: {topic.describe(task.answer)}")
                break
            out(f"Попробуйте ещё раз (попытка {attempts + 1} из {MAX_ATTEMPTS}).")

        if gave_up and attempts < MAX_ATTEMPTS:
            out(f"Правильный ответ: {topic.describe(task.answer)}")
        if gave_up:
            for line in topic.solution(task):
                out(line)
        profile.record(task.topic_id, task.difficulty, task.seed,
                       solved and attempts == 1, hints_shown, error_ids, max(attempts, 1))
        done += 1
        last.append(task.topic_id)
        out("")
    return done


# ----------------------------------------------------------------------- отчёт

def build_report(profile: Profile) -> str:
    lines = ["Освоение тем (оценка модели BKT):", ""]
    for tid, topic in TOPICS.items():
        st = profile.topics.get(tid)
        if st is None:
            continue
        bar = "█" * round(st.mastery * 20) + "·" * (20 - round(st.mastery * 20))
        lines.append(f"  {topic.title:<32} {bar} {st.mastery:4.0%}   "
                     f"задач: {st.attempts}, с первой попытки без подсказок: {st.correct}")
    lines.append("")
    if profile.errors:
        lines.append("Частые типичные ошибки:")
        for eid, count in sorted(profile.errors.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {count} × {MALRULE_TITLES.get(eid, eid)}")
    else:
        lines.append("Типичных ошибок пока не зафиксировано.")
    return "\n".join(lines)
