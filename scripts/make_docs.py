"""Генерирует docs/diagnosis.md и docs/session.md запуском настоящего кода.

Запуск из корня репозитория:  python scripts/make_docs.py
Ответы «ученика» в примере сеанса задаёт скрипт (чтобы сеанс был воспроизводимым),
весь остальной вывод — настоящий вывод программы.
"""
from __future__ import annotations

import contextlib
import io
import random
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mathtutor import cli, tutor  # noqa: E402
from mathtutor.profile import Profile  # noqa: E402
from mathtutor.topics import TOPICS, make_task  # noqa: E402

DOCS = ROOT / "docs"

# (заголовок, тема, сложность, предпочтительный seed, id типичной ошибки)
DIAGNOSIS_CASES = [
    ("Определитель: перепутан знак", "det", 2, 1, "det_sign"),
    ("Определитель 3×3: знаки в разложении по строке", "det", 2, 3, "laplace_no_signs"),
    ("Система: значения перепутаны местами", "system", 2, 3, "swapped_values"),
    ("Комбинаторика: учтён порядок", "comb", 1, 4, "order_counted"),
    ("Отношения: транзитивность проверена не полностью", "rel", 1, 7, "transitive_distinct_only"),
]


def run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue().rstrip()


def build_diagnosis() -> str:
    out = ["# Примеры диагностики ошибок", "",
           "Каждый неверный ответ ниже получен по конкретному «неверному правилу» (типичной ошибке); "
           "программа определяет его по значению ответа и объясняет. "
           "Файл сгенерирован `scripts/make_docs.py` запуском настоящих команд.", ""]
    for title, tid, d, seed, rule_id in DIAGNOSIS_CASES:
        topic = TOPICS[tid]
        for s in [seed, *range(1, 300)]:        # берём preferred seed, а если правило неприменимо, ближайший подходящий
            task = make_task(tid, d, s)
            rules = [r for r in topic.malrules(task) if r.id == rule_id]
            if rules:
                seed = s
                break
        else:
            raise RuntimeError(f"не нашёл задачу с правилом {rule_id}")
        wrong = topic.show(rules[0].value)
        show_cmd = ["task", tid, "--difficulty", str(d), "--seed", str(seed)]
        check_cmd = ["check", tid, "--difficulty", str(d), "--seed", str(seed), wrong]
        _, shown = run(show_cmd)
        code, checked = run(check_cmd)
        out += [f"## {title}", "", "```",
                "$ python -m mathtutor " + " ".join(shlex.quote(a) for a in show_cmd), shown, "",
                "$ python -m mathtutor " + " ".join(shlex.quote(a) for a in check_cmd), checked,
                f"(код возврата {code})", "```", ""]
    return "\n".join(out)


def build_session() -> str:
    profile, rng = Profile(), random.Random(11)
    transcript: list[str] = []
    state = {"task": None, "i": 0, "step": 0, "last": []}

    def source():
        while True:
            task = tutor.next_task(profile, rng, state["last"])
            state.update(task=task, step=0, i=state["i"] + 1)
            state["last"].append(task.topic_id)
            yield task

    def student(_prompt: str) -> str:
        task = state["task"]
        topic = TOPICS[task.topic_id]
        rules = topic.malrules(task)
        right = topic.show(task.answer)
        script = {1: [topic.show(rules[0].value) if rules else "100001", right],  # сначала типичная ошибка
                  2: ["h", "h", right],                                           # две подсказки
                  3: [right],                                                     # сразу верно
                  4: ["s"],                                                       # сдаётся: покажут решение
                  5: [right]}[state["i"]]
        answer = script[min(state["step"], len(script) - 1)]
        state["step"] += 1
        transcript.append(f"> {answer}")
        return answer

    tutor.run_practice(profile, 5, rng, student, transcript.append, task_source=source())
    return "\n".join([
        "# Пример сеанса", "",
        "Сеанс `python -m mathtutor practice -n 5`. Ответы «ученика» подставлял скрипт "
        "(`scripts/make_docs.py`), чтобы сеанс был воспроизводимым. Всё остальное (выбор тем, сложность, "
        "диагностика, подсказки, решение) — настоящий вывод программы.", "",
        "```", "\n".join(transcript).rstrip(), "```", "",
        "## Отчёт после сеанса", "", "```", tutor.build_report(profile), "```", ""])


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "diagnosis.md").write_text(build_diagnosis(), encoding="utf-8")
    (DOCS / "session.md").write_text(build_session(), encoding="utf-8")
    print("docs/diagnosis.md и docs/session.md обновлены")


if __name__ == "__main__":
    main()
