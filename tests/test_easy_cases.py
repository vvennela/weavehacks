from pathlib import Path

from benchmarks.grade import load_cases


def test_easy_cases_have_independently_checked_answers():
    cases = load_cases(Path(__file__).parents[1] / "benchmarks" / "easy_cases.json")
    expected = {
        "easy-01-add": 2 + 3,
        "easy-02-larger": max(4, 9),
        "easy-03-length": len(["red", "blue", "green"]),
        "easy-04-index": [10, 20][0],
        "easy-05-increment": 2 + 1,
        "easy-06-copy": {"count": 4}["count"],
        "easy-07-filter": [row["id"] for row in [{"id": "a", "ok": True}, {"id": "b", "ok": False}] if row["ok"]],
        "easy-08-upper": "cat".upper(),
    }
    assert {case["id"]: case["expected"] for case in cases} == expected
    assert len(cases) == 8
    assert all(case["difficulty"] == "easy" and case["max_tokens"] == 64 for case in cases)
