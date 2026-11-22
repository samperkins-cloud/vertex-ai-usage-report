import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from costsplit import NO_CALLS, model_key, split_cost

D = "2026-03-01"


def cost(model, amount, date=D):
    return {"date": date, "model_key": model, "cost": amount}


def call(person, model, n, date=D):
    return {"date": date, "person": person, "model_key": model, "calls": n}


class ModelKeyTests(unittest.TestCase):
    def test_billing_and_audit_names_meet(self):
        self.assertEqual(model_key("Gemini 2.5 Flash"), "gemini-2-5-flash")
        self.assertEqual(model_key("gemini-2.5-flash-001", strip_version=True), "gemini-2-5-flash")
        self.assertEqual(model_key("Claude Sonnet 4.5"), model_key("claude-sonnet-4-5", strip_version=True))
        self.assertEqual(model_key("claude-sonnet-4-5-20250929", strip_version=True), "claude-sonnet-4-5")

    def test_none(self):
        self.assertIsNone(model_key(None))


class SplitTests(unittest.TestCase):
    def by_person(self, rows, model):
        return {r["person"]: r for r in rows if r["model_key"] == model}

    def test_split_by_call_share(self):
        rows = split_cost([cost("m", 100.0)], [call("a", "m", 3), call("b", "m", 1)])
        got = self.by_person(rows, "m")
        self.assertAlmostEqual(got["a"]["est_cost"], 75.0)
        self.assertAlmostEqual(got["b"]["est_cost"], 25.0)
        self.assertAlmostEqual(got["a"]["share"], 0.75)

    def test_split_adds_back_to_cost(self):
        rows = split_cost([cost("m", 10.0), cost("n", 7.5)],
                          [call("a", "m", 1), call("b", "m", 2), call("c", "m", 4), call("a", "n", 5)])
        self.assertAlmostEqual(sum(r["est_cost"] for r in rows), 17.5)

    def test_model_with_no_calls_keeps_its_cost(self):
        rows = split_cost([cost("m", 12.0)], [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["person"], NO_CALLS)
        self.assertEqual(rows[0]["est_cost"], 12.0)
        self.assertIsNone(rows[0]["calls"])

    def test_calls_with_no_cost_get_no_estimate(self):
        rows = split_cost([], [call("a", "m", 2)])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["est_cost"])

    def test_person_on_two_models(self):
        rows = split_cost([cost("m", 10.0), cost("n", 40.0)],
                          [call("a", "m", 1), call("b", "m", 1), call("a", "n", 4)])
        a = [r for r in rows if r["person"] == "a"]
        self.assertEqual(len(a), 2)
        self.assertAlmostEqual(sum(r["est_cost"] for r in a), 5.0 + 40.0)
        self.assertAlmostEqual(self.by_person(rows, "n")["a"]["share"], 1.0)

    def test_days_do_not_mix(self):
        rows = split_cost([cost("m", 10.0, "2026-03-01"), cost("m", 20.0, "2026-03-02")],
                          [call("a", "m", 1, "2026-03-01"), call("b", "m", 1, "2026-03-02")])
        got = {r["date"]: r for r in rows}
        self.assertEqual(got["2026-03-01"]["person"], "a")
        self.assertAlmostEqual(got["2026-03-02"]["est_cost"], 20.0)

    def test_same_model_two_cost_lines_one_day(self):
        rows = split_cost([cost("m", 6.0), cost("m", 4.0)], [call("a", "m", 1), call("b", "m", 1)])
        self.assertAlmostEqual(self.by_person(rows, "m")["a"]["est_cost"], 5.0)


if __name__ == "__main__":
    unittest.main()
