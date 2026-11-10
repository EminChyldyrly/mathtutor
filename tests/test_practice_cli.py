import contextlib
import io
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathtutor import bkt, cli, tutor
from mathtutor.profile import Profile
from mathtutor.topics import TOPICS, make_task


def run_session(tasks, inputs, profile=None):
    """Запускает сеанс со сценарным вводом. Возвращает (профиль, вывод, число завершённых задач)."""
    profile = profile or Profile()
    feed = iter(inputs)
    lines = []

    def fake_input(prompt):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    done = tutor.run_practice(profile, len(tasks), random.Random(0), fake_input, lines.append,
                              task_source=iter(tasks))
    return profile, "\n".join(lines), done


class PracticeFlowTests(unittest.TestCase):
    def setUp(self):
        self.task = make_task("det", 1, 1)
        self.topic = TOPICS["det"]
        self.right = self.topic.show(self.task.answer)
        self.wrong = "100001"
        self.start = Profile().topics["det"].mastery

    def test_correct_first_try(self):
        p, out, done = run_session([self.task], [self.right])
        self.assertEqual(done, 1)
        self.assertIn("Верно!", out)
        self.assertAlmostEqual(p.topics["det"].mastery, bkt.update(self.start, True))
        self.assertEqual(p.history[0]["attempts"], 1)

    def test_format_errors_do_not_consume_attempts(self):
        p, out, _ = run_session([self.task], ["abc", "", "1/0", "xyz", self.right])
        self.assertEqual(out.count("Введите одно число"), 3)   # «1/0» даёт другое сообщение
        self.assertIn("Знаменатель", out)
        self.assertTrue(p.history[0]["correct_first_try"])
        self.assertEqual(p.history[0]["attempts"], 1)

    def test_hint_then_correct_counts_as_unsure(self):
        p, out, _ = run_session([self.task], ["h", self.right])
        self.assertIn("Подсказка 1/3", out)
        self.assertIn("неуверенный результат", out)
        self.assertAlmostEqual(p.topics["det"].mastery, bkt.update(self.start, False))
        self.assertEqual(p.history[0]["hints"], 1)

    def test_hints_run_out(self):
        _, out, _ = run_session([self.task], ["h", "h", "h", "h", self.right])
        self.assertIn("Подсказка 3/3", out)
        self.assertIn("Подсказки закончились", out)

    def test_second_attempt_correct_is_not_first_try(self):
        p, out, _ = run_session([self.task], [self.wrong, self.right])
        self.assertIn("Попробуйте ещё раз (попытка 2 из 3)", out)
        self.assertFalse(p.history[0]["correct_first_try"])
        self.assertEqual(p.history[0]["attempts"], 2)
        self.assertAlmostEqual(p.topics["det"].mastery, bkt.update(self.start, False))

    def test_three_wrong_answers_reveal_answer_and_solution(self):
        p, out, _ = run_session([self.task], [self.wrong] * 3)
        self.assertIn(f"Правильный ответ: {self.right}", out)
        self.assertEqual(out.count("Правильный ответ"), 1)
        for line in self.topic.solution(self.task):        # показано решение целиком
            self.assertIn(line, out)
        self.assertEqual(p.history[0]["attempts"], 3)
        self.assertFalse(p.history[0]["correct_first_try"])

    def test_typical_error_is_recorded_in_profile(self):
        wrong_by_rule = self.topic.show(self.topic.malrules(self.task)[0].value)
        rule_id = self.topic.malrules(self.task)[0].id
        p, out, _ = run_session([self.task], [wrong_by_rule, self.right])
        self.assertIn("Похоже на типичную ошибку", out)
        self.assertEqual(p.errors, {rule_id: 1})

    def test_give_up_shows_answer_once_and_counts_failure(self):
        p, out, _ = run_session([self.task], ["s"])
        self.assertEqual(out.count(f"Правильный ответ: {self.right}"), 1)
        self.assertEqual(p.history[0]["attempts"], 1)
        self.assertFalse(p.history[0]["correct_first_try"])
        self.assertAlmostEqual(p.topics["det"].mastery, bkt.update(self.start, False))

    def test_quit_immediately_records_nothing(self):
        p, out, done = run_session([self.task], ["q"])
        self.assertEqual((done, p.history), (0, []))
        self.assertIn("Сеанс завершён", out)

    def test_quit_after_starting_records_failure(self):
        p, _, done = run_session([self.task], ["h", "q"])
        self.assertEqual(done, 1)
        self.assertFalse(p.history[0]["correct_first_try"])

    def test_eof_acts_like_quit(self):
        p, out, done = run_session([self.task, make_task("det", 1, 2)], [])
        self.assertEqual((done, p.history), (0, []))
        self.assertIn("Сеанс завершён", out)

    def test_multi_task_session_updates_each_topic(self):
        tasks = [make_task("det", 1, 1), make_task("comb", 1, 2), make_task("rel", 1, 3)]
        answers = [TOPICS[t.topic_id].show(t.answer) for t in tasks]
        p, _, done = run_session(tasks, answers)
        self.assertEqual(done, 3)
        for t in tasks:
            self.assertGreater(p.topics[t.topic_id].mastery, 0.2)
        self.assertAlmostEqual(p.topics["system"].mastery, 0.2)      # нетронутая тема


class AdaptiveBehaviourTests(unittest.TestCase):
    def test_correct_answers_raise_difficulty_and_mistakes_lower_it(self):
        p = Profile()
        levels = []
        for s in range(8):
            levels.append(bkt.difficulty_for(p.topics["det"].mastery))
            p.record("det", 1, s, True, 0, [], 1)
        self.assertEqual(levels[0], 1)
        self.assertEqual(levels[-1], 3)
        self.assertEqual(levels, sorted(levels))             # без скачков вниз при серии успехов
        for s in range(8):
            p.record("det", 1, 100 + s, False, 0, [], 3)
        self.assertEqual(bkt.difficulty_for(p.topics["det"].mastery), 1)

    def test_weak_topic_gets_practised_more(self):
        p = Profile()
        for tid in p.topics:
            p.topics[tid].mastery = 0.9
        p.topics["rel"].mastery = 0.1
        rng = random.Random(4)
        picks = []
        last = []
        for _ in range(12):
            t = tutor.next_task(p, rng, last)
            picks.append(t.topic_id)
            last.append(t.topic_id)
        self.assertGreaterEqual(picks.count("rel"), 4)
        self.assertNotIn("rel rel rel", " ".join(picks).replace("  ", " ")
                         .replace("rel rel rel rel", "rel rel rel"))


class ReportTests(unittest.TestCase):
    def test_report_lists_topics_and_sorted_errors(self):
        p = Profile()
        p.record("det", 1, 1, False, 0, ["det_sign"], 2)
        p.record("det", 1, 2, False, 0, ["det_sign", "main_diagonal_only"], 2)
        text = tutor.build_report(p)
        for t in TOPICS.values():
            self.assertIn(t.title, text)
        self.assertLess(text.index("2 × перепутан знак результата"), text.index("1 × учтена только главная диагональ"))

    def test_empty_report(self):
        self.assertIn("пока не зафиксировано", tutor.build_report(Profile()))


def run_cli(*argv, stdin_inputs=None):
    out, err = io.StringIO(), io.StringIO()
    ctx = mock.patch("builtins.input", side_effect=stdin_inputs) if stdin_inputs is not None else contextlib.nullcontext()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), ctx:
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.profile = Path(self.tmp.name) / "profile.json"

    def test_topics_and_task(self):
        code, out, _ = run_cli("topics")
        self.assertEqual(code, 0)
        self.assertIn("det", out)
        code, out, _ = run_cli("task", "det", "--seed", "1")
        self.assertEqual(code, 0)
        self.assertIn("определитель", out)
        self.assertNotIn("Ответ:", out)
        _, out, _ = run_cli("task", "det", "--seed", "1", "--solution")
        self.assertIn("Ответ:", out)

    def test_same_seed_same_task(self):
        a = run_cli("task", "comb", "--difficulty", "2", "--seed", "9")[1]
        b = run_cli("task", "comb", "--difficulty", "2", "--seed", "9")[1]
        c = run_cli("task", "comb", "--difficulty", "2", "--seed", "10")[1]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_check_exit_codes(self):
        task = make_task("det", 1, 1)
        right = TOPICS["det"].show(task.answer)
        self.assertEqual(run_cli("check", "det", "--seed", "1", right)[0], 0)
        code, out, _ = run_cli("check", "det", "--seed", "1", "100001")
        self.assertEqual(code, 1)
        self.assertIn("Неверно", out)
        self.assertEqual(run_cli("check", "det", "--seed", "1", "abc")[0], 2)

    def test_check_diagnoses_known_mistake(self):
        task = make_task("det", 1, 1)
        wrong = TOPICS["det"].show(-task.answer)
        code, out, _ = run_cli("check", "det", "--seed", "1", wrong)
        self.assertEqual(code, 1)
        self.assertIn("знак результата", out)

    def test_hint_levels(self):
        self.assertEqual(run_cli("hint", "det", "--seed", "1", "2")[0], 0)
        code, _, err = run_cli("hint", "det", "--seed", "1", "9")
        self.assertEqual(code, 2)
        self.assertIn("Ошибка", err)

    def test_unknown_topic(self):
        code, _, err = run_cli("task", "nope")
        self.assertEqual(code, 2)
        self.assertIn("неизвестная тема", err)

    def test_practice_saves_progress_and_report_reads_it(self):
        task = tutor.next_task(Profile(), random.Random(5), [])      # тот же выбор, что сделает CLI с --seed 5
        right = TOPICS[task.topic_id].show(task.answer)
        code, out, _ = run_cli("practice", "-n", "1", "--seed", "5", "--profile", str(self.profile),
                               stdin_inputs=[right])
        self.assertEqual(code, 0)
        self.assertIn("Верно!", out)
        saved = Profile.load(self.profile)
        self.assertGreater(saved.topics[task.topic_id].mastery, 0.2)
        _, report, _ = run_cli("report", "--profile", str(self.profile))
        self.assertIn(TOPICS[task.topic_id].title, report)

    def test_practice_saves_progress_even_on_ctrl_c(self):
        task = tutor.next_task(Profile(), random.Random(6), [])
        feed = [TOPICS[task.topic_id].show(task.answer), KeyboardInterrupt()]
        code, _, _ = run_cli("practice", "-n", "3", "--seed", "6", "--profile", str(self.profile), stdin_inputs=feed)
        self.assertEqual(code, 130)
        self.assertEqual(Profile.load(self.profile).history[0]["seed"], task.seed)

    def test_corrupted_profile_is_reported_not_overwritten(self):
        self.profile.write_text("мусор", encoding="utf-8")
        code, _, err = run_cli("report", "--profile", str(self.profile))
        self.assertEqual(code, 2)
        self.assertIn("не удалось прочитать", err)
        code, _, _ = run_cli("practice", "-n", "1", "--profile", str(self.profile), stdin_inputs=["q"])
        self.assertEqual(code, 2)
        self.assertEqual(self.profile.read_text(encoding="utf-8"), "мусор")


if __name__ == "__main__":
    unittest.main()
