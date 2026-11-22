import re
from collections import defaultdict

NO_CALLS = "(no calls logged)"


def model_key(name, strip_version=False):
    if name is None:
        return None
    name = name.lower()
    if strip_version:
        name = re.sub(r"-(\d{3}|\d{8})$", "", name)
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def split_cost(cost_rows, call_rows):
    calls = defaultdict(lambda: defaultdict(int))
    for r in call_rows:
        calls[(r["date"], r["model_key"])][r["person"]] += r["calls"]

    costs = defaultdict(float)
    for r in cost_rows:
        costs[(r["date"], r["model_key"])] += r["cost"]

    out = []
    seen = set()
    for key, amount in sorted(costs.items()):
        seen.add(key)
        people = calls.get(key)
        if not people:
            out.append({"date": key[0], "model_key": key[1], "person": NO_CALLS,
                        "calls": None, "share": None, "est_cost": amount})
            continue
        total = sum(people.values())
        for person, n in sorted(people.items()):
            out.append({"date": key[0], "model_key": key[1], "person": person,
                        "calls": n, "share": n / total, "est_cost": amount * n / total})
    for key, people in calls.items():
        if key in seen:
            continue
        for person, n in sorted(people.items()):
            out.append({"date": key[0], "model_key": key[1], "person": person,
                        "calls": n, "share": None, "est_cost": None})
    return out
