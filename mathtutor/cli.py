"""Командная строка mathtutor."""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

from . import tutor
from .profile import Profile, ProfileError
from .topics import TOPICS, make_task

DEFAULT_PROFILE = Path.home() / ".mathtutor.json"


def _cmd_topics(args) -> int:
    for t in TOPICS.values():
        print(f"{t.id:<8} {t.title}")
    return 0


def _task_from_args(args):
    if args.topic not in TOPICS:
        raise ValueError(f"неизвестная тема {args.topic!r}. Доступны: {', '.join(TOPICS)}")
    return make_task(args.topic, args.difficulty, args.seed)


def _cmd_task(args) -> int:
    task = _task_from_args(args)
    print(task.statement)
    if args.solution:
        topic = TOPICS[task.topic_id]
        print(f"\nОтвет: {topic.describe(task.answer)}")
        for line in topic.solution(task):
            print(line)
    return 0


def _cmd_check(args) -> int:
    task = _task_from_args(args)
    fb = tutor.evaluate(task, args.answer)
    print("\n".join(fb.messages))
    return {"correct": 0, "wrong": 1, "format": 2}[fb.verdict]


def _cmd_hint(args) -> int:
    task = _task_from_args(args)
    hints = TOPICS[task.topic_id].hints(task)
    if not 1 <= args.level <= len(hints):
        raise ValueError(f"уровень подсказки: от 1 до {len(hints)}")
    print(hints[args.level - 1])
    return 0


def _cmd_practice(args) -> int:
    profile = Profile.load(args.profile)
    rng = random.Random(args.seed if args.seed is not None else int.from_bytes(os.urandom(8), "big"))
    try:
        # input передаём явно: имя ищется в момент вызова, поэтому ввод можно подменить в тестах
        tutor.run_practice(profile, args.n, rng, input_fn=input, out=print)
    finally:
        profile.save(args.profile)  # прогресс сохраняется даже при Ctrl+C
    print(f"Прогресс сохранён: {args.profile}")
    return 0


def _cmd_report(args) -> int:
    print(tutor.build_report(Profile.load(args.profile)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mathtutor", description="Тренажёр по математике с разбором типичных ошибок.")
    sub = p.add_subparsers(dest="command", required=True)

    def task_args(sp):
        sp.add_argument("topic", help=f"тема: {', '.join(TOPICS)}")
        sp.add_argument("--difficulty", type=int, default=1, choices=[1, 2, 3])
        sp.add_argument("--seed", type=int, default=1, help="номер варианта: тот же seed даёт ту же задачу")

    sp = sub.add_parser("topics", help="список тем"); sp.set_defaults(func=_cmd_topics)
    sp = sub.add_parser("task", help="показать задачу"); task_args(sp)
    sp.add_argument("--solution", action="store_true", help="показать ответ и решение")
    sp.set_defaults(func=_cmd_task)
    sp = sub.add_parser("check", help="проверить ответ (код возврата: 0 верно, 1 неверно, 2 не разобран)")
    task_args(sp); sp.add_argument("answer"); sp.set_defaults(func=_cmd_check)
    sp = sub.add_parser("hint", help="показать подсказку к задаче"); task_args(sp)
    sp.add_argument("level", type=int, nargs="?", default=1); sp.set_defaults(func=_cmd_hint)
    sp = sub.add_parser("practice", help="интерактивная тренировка с подбором задач")
    sp.add_argument("-n", type=int, default=5, help="число задач")
    sp.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    sp.add_argument("--seed", type=int, default=None, help="для воспроизводимого сеанса")
    sp.set_defaults(func=_cmd_practice)
    sp = sub.add_parser("report", help="освоение тем и частые ошибки")
    sp.add_argument("--profile", type=Path, default=DEFAULT_PROFILE); sp.set_defaults(func=_cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, ProfileError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nПрервано.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
