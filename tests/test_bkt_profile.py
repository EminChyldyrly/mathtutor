import json
import os
import random
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from mathtutor import bkt
from mathtutor.profile import HISTORY_LIMIT, Profile, ProfileError


def bayes_reference(p, correct, init, learn, slip, guess):
    """Независимая реализация на точных дробях: прямое применение формулы Байеса."""
    p, learn, slip, guess = map(Fraction, (p, learn, slip, guess))
    if correct:
        post = (p * (1 - slip)) / (p * (1 - slip) + (1 - p) * guess)
    else:
        post = (p * slip) / (p * slip + (1 - p) * (1 - guess))
    return post + (1 - post) * learn


class BKTTests(unittest.TestCase):
    def test_matches_exact_bayes_reference(self):
        rng = random.Random(1)
        for _ in range(500):
            params = bkt.BKTParams(p_init=0.2, p_learn=rng.choice([0.05, 0.1, 0.2, 0.3]),
                                   p_slip=rng.choice([0.05, 0.1, 0.2]), p_guess=rng.choice([0.1, 0.2, 0.25]))
            p = rng.random() * 0.98 + 0.01
            for correct in (True, False):
                got = bkt.update(p, correct, params)
                want = float(bayes_reference(Fraction(p), correct, params.p_init, params.p_learn,
                                             params.p_slip, params.p_guess))
                self.assertAlmostEqual(got, want, places=9)

    def test_known_numbers(self):
        # p=0.2, верно: 0.2·0.9 / (0.2·0.9 + 0.8·0.2) = 0.18/0.34 ≈ 0.5294; затем + (1−0.5294)·0.15 ≈ 0.6
        self.assertAlmostEqual(bkt.update(0.2, True), 0.6, places=3)
        # p=0.9, ошибка: 0.09 / (0.09 + 0.08) ≈ 0.5294; затем ≈ 0.6
        self.assertAlmostEqual(bkt.update(0.9, False), 0.6, places=3)

    def test_correct_raises_and_wrong_lowers_the_estimate_beyond_learning(self):
        for p in (0.05, 0.3, 0.5, 0.8):
            self.assertGreater(bkt.update(p, True), p)
        self.assertLess(bkt.update(0.95, False), 0.95)
        self.assertLess(bkt.update(0.9, False), bkt.update(0.9, True))

    def test_stays_in_unit_interval_and_converges(self):
        rng = random.Random(2)
        p = 0.2
        for _ in range(2000):
            p = bkt.update(p, rng.random() < 0.5)
            self.assertTrue(0.0 <= p <= 1.0)
        p = 0.2
        for _ in range(50):
            p = bkt.update(p, True)
        self.assertGreater(p, 0.99)
        self.assertLessEqual(p, 1.0)

    def test_streak_of_wrong_answers_keeps_mastery_low(self):
        p = 0.2
        for _ in range(20):
            p = bkt.update(p, False)
        self.assertLess(p, 0.2)

    def test_difficulty_thresholds(self):
        cases = {0.0: 1, 0.39: 1, 0.4: 2, 0.74: 2, 0.75: 3, 1.0: 3}
        for m, d in cases.items():
            self.assertEqual(bkt.difficulty_for(m), d, m)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "p.json"

    def test_record_updates_bkt_once_per_task(self):
        p = Profile()
        before = p.topics["det"].mastery
        p.record("det", 1, 5, True, 0, [], 1)
        self.assertAlmostEqual(p.topics["det"].mastery, bkt.update(before, True))
        self.assertEqual((p.topics["det"].attempts, p.topics["det"].correct), (1, 1))

    def test_hint_or_retry_counts_as_not_observed_correct(self):
        p = Profile()
        before = p.topics["comb"].mastery
        p.record("comb", 1, 5, True, 1, [], 1)               # верно, но с подсказкой
        self.assertAlmostEqual(p.topics["comb"].mastery, bkt.update(before, False))
        self.assertEqual(p.topics["comb"].correct, 0)
        mid = p.topics["comb"].mastery
        p.record("comb", 1, 6, False, 0, ["order_counted"], 2)
        self.assertAlmostEqual(p.topics["comb"].mastery, bkt.update(mid, False))

    def test_error_counts_accumulate(self):
        p = Profile()
        p.record("det", 1, 1, False, 0, ["det_sign"], 2)
        p.record("det", 1, 2, False, 0, ["det_sign", "main_diagonal_only"], 1)
        self.assertEqual(p.errors, {"det_sign": 2, "main_diagonal_only": 1})

    def test_history_is_capped(self):
        p = Profile()
        for i in range(HISTORY_LIMIT + 25):
            p.record("det", 1, i, True, 0, [], 1)
        self.assertEqual(len(p.history), HISTORY_LIMIT)
        self.assertEqual(p.history[-1]["seed"], HISTORY_LIMIT + 24)

    def test_save_load_roundtrip(self):
        p = Profile()
        p.record("det", 2, 11, False, 2, ["det_sign"], 3)
        p.record("rel", 1, 12, True, 0, [], 1)
        p.save(self.path)
        q = Profile.load(self.path)
        self.assertEqual(q.to_json(), p.to_json())
        self.assertEqual(q.topics["det"].mastery, p.topics["det"].mastery)

    def test_missing_file_gives_fresh_profile(self):
        p = Profile.load(self.path)
        self.assertEqual(p.errors, {})
        self.assertTrue(all(abs(s.mastery - 0.2) < 1e-12 for s in p.topics.values()))

    def test_corrupted_file_raises_and_is_not_overwritten(self):
        self.path.write_text("{ это не json", encoding="utf-8")
        with self.assertRaises(ProfileError):
            Profile.load(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{ это не json")

    def test_invalid_structures_rejected(self):
        good = Profile().to_json()
        bad_variants = [
            [], {"version": 2}, {**good, "topics": {"det": {"mastery": 1.5, "attempts": 0, "correct": 0}}},
            {**good, "topics": {"det": {"mastery": "x", "attempts": 0, "correct": 0}}},
            {**good, "topics": {"det": {"mastery": 0.5}}}, {"version": 1},
        ]
        for data in bad_variants:
            with self.assertRaises(ProfileError, msg=str(data)[:60]):
                Profile.from_json(data)

    def test_save_is_atomic_and_leaves_no_temp_files(self):
        p = Profile()
        p.save(self.path)
        p.record("det", 1, 1, True, 0, [], 1)
        p.save(self.path)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["p.json"])
        json.loads(self.path.read_text(encoding="utf-8"))   # корректный JSON

    def test_failed_save_keeps_old_file(self):
        p = Profile()
        p.save(self.path)
        old = self.path.read_text(encoding="utf-8")
        p.history.append({"bad": object()})                  # json.dump упадёт
        with self.assertRaises(TypeError):
            p.save(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), old)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["p.json"])

    def test_crash_during_replace_keeps_old_file_intact(self):
        """Сбой на самом шаге замены файла не должен портить прежний профиль."""
        p = Profile()
        p.record("det", 1, 1, True, 0, [], 1)
        p.save(self.path)
        old = self.path.read_text(encoding="utf-8")
        p.record("det", 1, 2, False, 0, ["det_sign"], 2)
        from unittest import mock
        with mock.patch("mathtutor.profile.os.replace", side_effect=OSError("диск отвалился")):
            with self.assertRaises(OSError):
                p.save(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), old)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["p.json"])    # временный файл убран

    def test_unicode_error_names_survive(self):
        p = Profile()
        p.errors["ошибка"] = 2
        p.save(self.path)
        self.assertEqual(Profile.load(self.path).errors, {"ошибка": 2})


if __name__ == "__main__":
    unittest.main()
