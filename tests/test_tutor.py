"""Тесты проверки ответов и диагностики типичных ошибок."""
import random
import unittest
from fractions import Fraction

from mathtutor import tutor
from mathtutor.topics import MALRULE_TITLES, TOPICS, make_task
from mathtutor.topics.base import Task

SEEDS = range(1, 41)


def all_tasks():
    for tid in TOPICS:
        for d in (1, 2, 3):
            for s in SEEDS:
                yield make_task(tid, d, s)


class AnswerParsingTests(unittest.TestCase):
    def test_show_then_parse_roundtrip_and_correct(self):
        for t in all_tasks():
            topic = TOPICS[t.topic_id]
            text = topic.show(t.answer)
            self.assertEqual(topic.parse(t, text), t.answer, text)
            self.assertTrue(tutor.evaluate(t, text).correct, text)

    def test_scalar_formats(self):
        t = Task("det", 1, 0, "", {"matrix": [[1, 0], [0, 5]]}, Fraction(5))
        for ok in ("5", " 5 ", "+5", "5.0", "5,0", "10/2"):
            self.assertTrue(tutor.evaluate(t, ok).correct, ok)
        for bad in ("", "abc", "5 5", "1 000", "5!", "--5", "5/0"):
            self.assertEqual(tutor.evaluate(t, bad).verdict, "format", bad)

    def test_unicode_minus_accepted(self):
        t = Task("det", 1, 0, "", {"matrix": [[1, 2], [3, 4]]}, Fraction(-2))
        self.assertTrue(tutor.evaluate(t, "−2").correct)

    def test_system_formats(self):
        t = make_task("system", 2, 3)          # ответ (2, 5, 1)
        for ok in ("2 5 1", "2, 5, 1", "(2; 5; 1)", "[2,5,1]", "x=2, y=5, z=1", "z=1 y=5 x=2", "x = 2; y = 5; z = 1"):
            self.assertTrue(tutor.evaluate(t, ok).correct, ok)
        for bad in ("2 5", "2 5 1 7", "x=2, y=5", "x=2, x=5, z=1", "a=2, b=5, c=1", ""):
            self.assertEqual(tutor.evaluate(t, bad).verdict, "format", bad)

    def test_relation_formats(self):
        t = Task("rel", 1, 0, "", {"A": [1, 2], "R": [(1, 1), (2, 2)]}, frozenset({"refl", "sym", "antisym", "trans"}))
        for ok in ("1 2 3 4", "4,3,2,1", "1;2;3;4", "рефлексивность симметричность антисимметричность транзитивность"):
            self.assertTrue(tutor.evaluate(t, ok).correct, ok)
        t0 = Task("rel", 1, 0, "", {"A": [1, 2], "R": [(1, 2)]}, frozenset())
        for ok in ("0", "нет", "-", "ничего"):
            self.assertTrue(tutor.evaluate(t0, ok).correct, ok)
        for bad in ("", "5", "1 7", "привет"):
            self.assertEqual(tutor.evaluate(t, bad).verdict, "format", bad)

    def test_format_error_is_not_a_wrong_answer(self):
        fb = tutor.evaluate(make_task("det", 1, 1), "abc")
        self.assertEqual(fb.verdict, "format")
        self.assertEqual(fb.error_ids, [])

    def test_fuzz_never_raises(self):
        rng = random.Random(0)
        alphabet = "0123456789 ,;-/.()=xyzабв−+\t"
        tasks = [make_task(tid, d, 5) for tid in TOPICS for d in (1, 2, 3)]
        for _ in range(500):
            raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 16)))
            for t in tasks:
                fb = tutor.evaluate(t, raw)
                self.assertIn(fb.verdict, {"correct", "wrong", "format"})
                self.assertTrue(fb.messages)


class MalruleTests(unittest.TestCase):
    def test_every_malrule_answer_is_diagnosed(self):
        """Ответ по каждому «неверному правилу» определяется как неверный и получает своё объяснение."""
        used_ids = set()
        for t in all_tasks():
            topic = TOPICS[t.topic_id]
            for rule in topic.malrules(t):
                self.assertFalse(topic.equal(rule.value, t.answer), (t.topic_id, rule.id))
                fb = tutor.evaluate(t, topic.show(rule.value))
                self.assertEqual(fb.verdict, "wrong", (t.statement, rule.id))
                self.assertIn(rule.id, fb.error_ids)
                self.assertTrue(any(rule.explanation in m for m in fb.messages))
                used_ids.add(rule.id)
        # каждое описанное правило встречается на практике; каждое встреченное — описано
        self.assertEqual(used_ids, set(MALRULE_TITLES))

    def test_unrelated_wrong_answer_gets_no_malrule(self):
        t = make_task("det", 1, 1)
        topic = TOPICS["det"]
        forbidden = {r.value for r in topic.malrules(t)} | {t.answer}
        wrong = Fraction(100001)
        self.assertNotIn(wrong, forbidden)
        fb = tutor.evaluate(t, str(wrong))
        self.assertEqual(fb.verdict, "wrong")
        self.assertEqual(fb.error_ids, [])
        self.assertEqual(fb.messages, ["Неверно."])

    def test_correct_answer_wins_even_if_it_equals_a_malrule_value(self):
        # det [[3,0],[0,1]] = 3 = только главная диагональ: верный ответ не должен считаться ошибкой
        t = Task("det", 1, 0, "", {"matrix": [[3, 0], [0, 1]]}, Fraction(3))
        self.assertTrue(tutor.evaluate(t, "3").correct)

    def test_determinant_rules_with_known_matrix(self):
        t = Task("det", 1, 0, "", {"matrix": [[2, 3], [1, 4]]}, Fraction(5))   # 2·4 − 3·1 = 5
        self.assertEqual(tutor.evaluate(t, "-5").error_ids, ["det_sign"])
        self.assertEqual(tutor.evaluate(t, "8").error_ids, ["main_diagonal_only"])
        self.assertEqual(tutor.evaluate(t, "11").error_ids, ["det_plus_between"])

    def test_sarrus_and_laplace_rules_with_known_matrix(self):
        m = [[1, 2, 3], [0, 1, 4], [5, 6, 0]]     # det = 1
        t = Task("det", 2, 0, "", {"matrix": m}, Fraction(1))
        self.assertEqual(tutor.evaluate(t, "-1").error_ids, ["det_sign"])
        self.assertEqual(tutor.evaluate(t, "1").verdict, "correct")
        # все шесть Саррюса с «+»: 0+20+0 + 15+0+0 -> pos = 0+20+0 = 20 ... считаем независимо
        pos = 1 * 1 * 0 + 2 * 4 * 5 + 3 * 0 * 6
        neg = 3 * 1 * 5 + 1 * 4 * 6 + 2 * 0 * 0
        self.assertEqual(pos - neg, 1)
        self.assertIn("sarrus_all_plus", tutor.evaluate(t, str(pos + neg)).error_ids)
        # разложение по первой строке без чередования знаков
        minors = [1 * 0 - 4 * 6, 0 * 0 - 4 * 5, 0 * 6 - 1 * 5]
        no_signs = 1 * minors[0] + 2 * minors[1] + 3 * minors[2]
        self.assertIn("laplace_no_signs", tutor.evaluate(t, str(no_signs)).error_ids)

    def test_system_rules_and_residuals(self):
        t = make_task("system", 2, 3)        # ответ (2, 5, 1)
        fb = tutor.evaluate(t, "5 2 1")
        self.assertEqual(fb.error_ids, ["swapped_values"])
        fb = tutor.evaluate(t, "-2 5 1")
        self.assertEqual(fb.error_ids, ["sign_error"])
        self.assertTrue(any("x" in m and "знак" in m for m in fb.messages))

    def test_system_residual_lines_match_actual_failures(self):
        rng = random.Random(1)
        for t in (make_task("system", d, s) for d in (1, 2, 3) for s in SEEDS):
            n = len(t.answer)
            guess = tuple(Fraction(rng.randint(-6, 6)) for _ in range(n))
            if guess == t.answer:
                continue
            fb = tutor.evaluate(t, " ".join(str(int(v)) for v in guess))
            failing = [k for k, (row, rhs) in enumerate(zip(t.data["A"], t.data["b"]), 1)
                       if sum(c * v for c, v in zip(row, guess)) != rhs]
            reported = [k for k in range(1, n + 1)
                        if any(m.startswith(f"Подстановка в уравнение {k} ") for m in fb.messages)]
            self.assertEqual(reported, failing)
            self.assertTrue(failing)          # единственное решение: любой иной вектор что-то нарушает

    def test_relation_rules_with_known_relations(self):
        # транзитивность «только для различных»: (1,2),(2,1) без (1,1)
        t = Task("rel", 1, 0, "", {"A": [1, 2], "R": [(1, 2), (2, 1)]}, frozenset({"sym"}))
        fb = tutor.evaluate(t, "2 4")
        self.assertEqual(fb.error_ids, ["transitive_distinct_only"])
        self.assertTrue(any("есть пары (1, 2) и (2, 1), но нет пары (1, 1)" in m for m in fb.messages))
        # антисимметричность как «не симметричность»
        t = Task("rel", 1, 0, "", {"A": [1, 2], "R": [(1, 1), (2, 2)]}, frozenset({"refl", "sym", "antisym", "trans"}))
        self.assertEqual(tutor.evaluate(t, "1 2 4").error_ids, ["antisym_is_not_sym"])
        # рефлексивность по наличию хотя бы одной петли
        t = Task("rel", 1, 0, "", {"A": [1, 2, 3], "R": [(1, 1), (1, 2)]}, frozenset({"antisym", "trans"}))
        self.assertEqual(tutor.evaluate(t, "1 3 4").error_ids, ["reflexive_if_any_loop"])

    def test_relation_explanations_cover_both_directions(self):
        t = Task("rel", 1, 0, "", {"A": [1, 2], "R": [(1, 2)]}, frozenset({"antisym", "trans"}))
        fb = tutor.evaluate(t, "1 2")     # лишнее: refl, sym; пропущено: antisym, trans
        text = "\n".join(fb.messages)
        self.assertIn("в отношении нет пары (1, 1)", text)            # refl заявлена зря: дан контрпример
        self.assertIn("есть пара (1, 2), но нет пары (2, 1)", text)    # sym заявлена зря
        self.assertIn("Антисимметричность: вы считаете, что она не выполняется", text)
        self.assertIn("Транзитивность: вы считаете, что она не выполняется", text)


class CombinatoricsRuleSpecTests(unittest.TestCase):
    """Значения «типичных ошибок» сверяются с независимо записанной спецификацией,
    а не с самим кодом диагностики."""

    @staticmethod
    def expected_wrong(kind, n, k, word):
        from math import comb, factorial, perm
        wrong = {"C": {perm(n, k), n ** k},
                 "A": {comb(n, k), n ** k},
                 "rep_arr": {comb(n, k) if k <= n else None, perm(n, k) if k <= n else None},
                 "multiset": {factorial(n)},
                 "rep_comb": {comb(n, k) if k <= n else None, n ** k, comb(n + k, k)}}[kind]
        return {Fraction(v) for v in wrong if v is not None}

    def test_rule_values_are_exactly_the_specified_wrong_formulas(self):
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("comb", d, s)
                kind, n, k, word = (t.data[x] for x in ("kind", "n", "k", "word"))
                got = {r.value for r in TOPICS["comb"].malrules(t)}
                want = self.expected_wrong(kind, n, k, word) - {t.answer}
                self.assertEqual(got, want, (kind, n, k, word))


class HintContentTests(unittest.TestCase):
    def test_system_elimination_hint_really_zeroes_the_coefficient(self):
        import re
        checked = 0
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("system", d, s)
                a = t.data["A"]
                hint = TOPICS["system"].hints(t)[1]
                m = re.search(r"из уравнения (\d+), вычтите из него уравнение (\d+), умноженное на (-?\d+(?:/\d+)?)", hint)
                if m is None:
                    self.assertIn("уже отсутствует", hint)
                    # такая подсказка допустима, только если x входит ровно в одно уравнение
                    self.assertEqual(sum(1 for row in a if row[0] != 0), 1)
                    continue
                other, pivot, k = int(m[1]) - 1, int(m[2]) - 1, Fraction(m[3])
                self.assertNotEqual(a[pivot][0], 0)
                self.assertEqual(a[other][0] - k * a[pivot][0], 0, hint)
                checked += 1
        self.assertGreater(checked, 80)


class DescribeTests(unittest.TestCase):
    def test_describe_is_readable_and_contains_the_parsable_form(self):
        for t in all_tasks():
            topic = TOPICS[t.topic_id]
            self.assertTrue(topic.describe(t.answer).startswith(topic.show(t.answer)))

    def test_relation_answer_is_spelled_out(self):
        topic = TOPICS["rel"]
        self.assertEqual(topic.describe(frozenset()), "0 (ни одно свойство не выполняется)")
        self.assertEqual(topic.describe(frozenset({"refl", "trans"})), "1 4 (рефлексивность, транзитивность)")


class HelpTests(unittest.TestCase):
    def test_three_distinct_hints_for_every_task(self):
        for t in all_tasks():
            hints = TOPICS[t.topic_id].hints(t)
            self.assertEqual(len(hints), 3, t.topic_id)
            self.assertTrue(all(h.strip() for h in hints))
            self.assertEqual(len(set(hints)), 3)

    def test_system_hint_reveals_only_last_unknown(self):
        t = make_task("system", 2, 3)    # (2, 5, 1)
        hint = TOPICS["system"].hints(t)[2]
        self.assertIn("z = 1", hint)
        self.assertNotIn("x = 2", hint)
        self.assertNotIn("y = 5", hint)

    def test_solutions_state_the_correct_answer(self):
        for t in all_tasks():
            lines = TOPICS[t.topic_id].solution(t)
            self.assertTrue(lines)
            if t.topic_id == "det":
                self.assertIn(TOPICS["det"].show(t.answer), lines[-1])
            if t.topic_id == "comb":
                self.assertIn(TOPICS["comb"].show(t.answer), lines[-1])

    def test_relation_solution_matches_answer(self):
        for t in (make_task("rel", d, s) for d in (1, 2, 3) for s in SEEDS):
            lines = TOPICS["rel"].solution(t)
            holds = {name for name, line in zip(["refl", "sym", "antisym", "trans"], lines)
                     if "выполняется." in line and "не выполняется" not in line}
            self.assertEqual(holds, set(t.answer))


class TopicSelectionTests(unittest.TestCase):
    def test_picks_weakest_topic_and_is_deterministic(self):
        from mathtutor.profile import Profile
        p = Profile()
        for tid in p.topics:
            p.topics[tid].mastery = 0.9
        p.topics["comb"].mastery = 0.1
        for seed in range(10):
            self.assertEqual(tutor.choose_topic(p, random.Random(seed), []), "comb")
        a = [tutor.choose_topic(Profile(), random.Random(3), []) for _ in range(3)]
        self.assertEqual(len(set(a)), 1)

    def test_never_three_in_a_row(self):
        from mathtutor.profile import Profile
        p = Profile()
        for tid in p.topics:
            p.topics[tid].mastery = 0.9
        p.topics["comb"].mastery = 0.0
        for seed in range(20):
            self.assertNotEqual(tutor.choose_topic(p, random.Random(seed), ["comb", "comb"]), "comb")

    def test_difficulty_follows_mastery(self):
        from mathtutor.profile import Profile
        p = Profile()
        p.topics["det"].mastery = 0.9
        for tid in ("system", "comb", "rel"):
            p.topics[tid].mastery = 0.95
        t = tutor.next_task(p, random.Random(1), [])
        self.assertEqual(t.difficulty, 3)


if __name__ == "__main__":
    unittest.main()
