"""Тесты генераторов задач: ответы сверяются с независимыми реализациями."""
import itertools
import unittest
from collections import Counter
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, permutations, product

from mathtutor.topics import TOPICS, make_task

SEEDS = range(1, 61)


def laplace_det(m):
    n = len(m)
    if n == 1:
        return m[0][0]
    return sum((-1) ** j * m[0][j] * laplace_det([row[:j] + row[j + 1:] for row in m[1:]])
               for j in range(n))


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_task_and_different_seeds_vary(self):
        for tid in TOPICS:
            for d in (1, 2, 3):
                a, b = make_task(tid, d, 7), make_task(tid, d, 7)
                self.assertEqual((a.statement, a.data, a.answer), (b.statement, b.data, b.answer))
                statements = {make_task(tid, d, s).statement for s in SEEDS}
                self.assertGreater(len(statements), 20, f"{tid} d={d}: мало разных задач")

    def test_invalid_arguments(self):
        with self.assertRaises(KeyError):
            make_task("nope", 1, 1)
        with self.assertRaises(ValueError):
            make_task("det", 4, 1)


class DeterminantTasks(unittest.TestCase):
    def test_answer_matches_laplace_expansion_and_is_nonzero(self):
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("det", d, s)
                m = t.data["matrix"]
                self.assertEqual(len(m), 2 if d == 1 else 3)
                self.assertEqual(t.answer, laplace_det(m))
                self.assertNotEqual(t.answer, 0)


class SystemTasks(unittest.TestCase):
    def test_solution_satisfies_every_equation_and_system_is_nonsingular(self):
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("system", d, s)
                a, b = t.data["A"], t.data["b"]
                self.assertNotEqual(laplace_det(a), 0)
                for row, rhs in zip(a, b):
                    self.assertEqual(sum(c * v for c, v in zip(row, t.answer)), rhs)

    def test_statement_lists_each_equation(self):
        t = make_task("system", 2, 3)
        self.assertEqual(t.statement.count("="), 3)
        self.assertIn("x, y, z", t.statement)


class CombinatoricsTasks(unittest.TestCase):
    def test_answers_match_brute_force_enumeration(self):
        seen = Counter()
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("comb", d, s)
                kind, n, k, word = (t.data[x] for x in ("kind", "n", "k", "word"))
                seen[kind] += 1
                if kind == "C":
                    expected = sum(1 for _ in combinations(range(n), k))
                elif kind == "A":
                    expected = sum(1 for _ in permutations(range(n), k))
                elif kind == "rep_arr":
                    if n ** k > 60000:
                        continue
                    expected = sum(1 for _ in product(range(n), repeat=k))
                elif kind == "rep_comb":
                    expected = sum(1 for _ in combinations_with_replacement(range(n), k))
                else:
                    if len(word) > 7:
                        continue
                    expected = len(set(permutations(word)))
                self.assertEqual(t.answer, expected, (kind, n, k, word))
        for kind in ("C", "A", "rep_arr", "rep_comb", "multiset"):
            self.assertGreater(seen[kind], 3, f"вид задач {kind} почти не встречается")

    def test_long_word_formula(self):
        # МАТЕМАТИКА: М2 А3 Т2 Е1 И1 К1 → 10! / (2!·3!·2!)
        from mathtutor.topics.combinatorics import multiset_count
        self.assertEqual(multiset_count("МАТЕМАТИКА"), 151200)


class RelationTasks(unittest.TestCase):
    @staticmethod
    def brute(a, r):
        r = set(map(tuple, r))
        out = set()
        if all((x, x) in r for x in a):
            out.add("refl")
        if all(((y, x) in r) for (x, y) in itertools.product(a, a) if (x, y) in r):
            out.add("sym")
        if all(not ((x, y) in r and (y, x) in r and x != y) for x, y in itertools.product(a, a)):
            out.add("antisym")
        if all(((x, z) in r) for x, y, z in itertools.product(a, a, a) if (x, y) in r and (y, z) in r):
            out.add("trans")
        return frozenset(out)

    def test_answers_match_definitions(self):
        for d in (1, 2, 3):
            for s in SEEDS:
                t = make_task("rel", d, s)
                self.assertEqual(t.answer, self.brute(t.data["A"], t.data["R"]))

    def test_tasks_have_varied_answers(self):
        answers = {make_task("rel", d, s).answer for d in (1, 2, 3) for s in SEEDS}
        self.assertGreater(len(answers), 5, "слишком мало разных наборов свойств")
        self.assertIn(frozenset(), answers)                      # есть задачи «ничего не выполняется»
        self.assertTrue(any(len(a) >= 3 for a in answers))       # и задачи «почти всё выполняется»

    def test_relation_is_never_empty(self):
        for d in (1, 2, 3):
            for s in SEEDS:
                self.assertTrue(make_task("rel", d, s).data["R"])


if __name__ == "__main__":
    unittest.main()
