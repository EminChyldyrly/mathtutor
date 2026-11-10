"""Реестр тем."""
from __future__ import annotations

from .base import AnswerFormatError, Malrule, Task, Topic
from .combinatorics import CombinatoricsTopic
from .determinant import DeterminantTopic
from .relations import RelationsTopic
from .system import SystemTopic

TOPICS: dict[str, Topic] = {t.id: t for t in (
    DeterminantTopic(), SystemTopic(), CombinatoricsTopic(), RelationsTopic())}

MALRULE_TITLES: dict[str, str] = {}
for _t in TOPICS.values():
    MALRULE_TITLES.update(_t.malrule_titles)


def make_task(topic_id: str, difficulty: int, seed: int) -> Task:
    if topic_id not in TOPICS:
        raise KeyError(f"неизвестная тема: {topic_id!r}. Доступны: {', '.join(TOPICS)}")
    return TOPICS[topic_id].make(difficulty, seed)


__all__ = ["TOPICS", "MALRULE_TITLES", "make_task", "Task", "Topic", "Malrule", "AnswerFormatError"]
