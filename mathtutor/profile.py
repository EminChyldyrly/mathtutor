"""Профиль ученика: освоение тем, статистика ошибок, история. Хранится в JSON."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import bkt
from .topics import TOPICS

HISTORY_LIMIT = 500


class ProfileError(Exception):
    """Файл профиля повреждён или имеет неожиданный формат."""


@dataclass
class TopicStats:
    mastery: float = bkt.BKTParams().p_init
    attempts: int = 0
    correct: int = 0


@dataclass
class Profile:
    topics: dict[str, TopicStats] = field(default_factory=lambda: {t: TopicStats() for t in TOPICS})
    errors: dict[str, int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def record(self, topic_id: str, difficulty: int, seed: int, correct_first: bool,
               hints_used: int, error_ids: list[str], attempts: int) -> None:
        """Записывает итог задачи. В BKT идёт одно наблюдение на задачу:
        верно с первой попытки и без подсказок."""
        stats = self.topics.setdefault(topic_id, TopicStats())
        observed_correct = correct_first and hints_used == 0
        stats.mastery = bkt.update(stats.mastery, observed_correct)
        stats.attempts += 1
        stats.correct += int(observed_correct)
        for eid in error_ids:
            self.errors[eid] = self.errors.get(eid, 0) + 1
        self.history.append({"topic": topic_id, "difficulty": difficulty, "seed": seed,
                             "correct_first_try": correct_first, "hints": hints_used,
                             "attempts": attempts, "errors": list(error_ids)})
        del self.history[:-HISTORY_LIMIT]

    # ------------------------------------------------------------- сохранение
    def to_json(self) -> dict:
        return {"version": 1,
                "topics": {k: {"mastery": v.mastery, "attempts": v.attempts, "correct": v.correct}
                           for k, v in self.topics.items()},
                "errors": self.errors, "history": self.history}

    @classmethod
    def from_json(cls, data: object) -> "Profile":
        try:
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("неизвестная версия формата")
            prof = cls()
            for tid, v in data["topics"].items():
                m = float(v["mastery"])
                if not 0.0 <= m <= 1.0:
                    raise ValueError(f"освоение вне [0, 1]: {m}")
                prof.topics[tid] = TopicStats(m, int(v["attempts"]), int(v["correct"]))
            prof.errors = {str(k): int(v) for k, v in data["errors"].items()}
            prof.history = list(data["history"])
            return prof
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ProfileError(f"неверный формат профиля: {exc}") from exc

    def save(self, path: str | Path) -> None:
        """Атомарная запись: при сбое старый файл не портится."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_json(), fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        """Нет файла — новый профиль. Повреждённый файл — ProfileError (не перезаписываем)."""
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProfileError(f"не удалось прочитать {path}: {exc}") from exc
        return cls.from_json(data)
