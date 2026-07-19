"""
Scrollytelling Data Builder Tests.

viz/story/build_story_data.py precomputes every step of the story into
story.json — the JS does zero aggregation, so a bad number here ships
straight to the reader. These tests cover the one thing that's cheap to
verify without a live DB connection (_clean_nans, pure and deterministic)
and, when a real story.json is present, that every expected step key exists
and no NaN/Infinity leaked through (Python's json module accepts those as a
non-standard extension on load, so a NaN can silently round-trip through
json.dump/json.load without ever raising).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

STORY_DIR = Path(__file__).resolve().parent.parent / "viz" / "story"
sys.path.insert(0, str(STORY_DIR))

from build_story_data import _clean_nans  # noqa: E402

STORY_JSON_PATH = STORY_DIR / "data" / "story.json"

EXPECTED_TOP_LEVEL_KEYS = {"meta", "hook", "scale", "funnel", "visa", "skills", "salary_score", "close"}
EXPECTED_KEYS_BY_STEP = {
    "scale": {"total_scraped", "date_start", "date_end", "weeks", "source_count", "sources"},
    "funnel": {"stages", "tiers", "qualified_at_threshold", "match_threshold"},
    "visa": {"total_postings", "claims_sponsorship", "employers_checked", "employers_licensed", "pictogram_n", "pictogram_highlighted"},
    "skills": {"weeks", "series", "rising", "cooling"},
    "salary_score": {"points", "n"},
}


class TestCleanNans:
    def test_replaces_nan_with_none(self):
        assert _clean_nans({"score": float("nan")}) == {"score": None}

    def test_replaces_infinity_with_none(self):
        assert _clean_nans({"a": float("inf"), "b": float("-inf")}) == {"a": None, "b": None}

    def test_leaves_normal_floats_and_ints_untouched(self):
        assert _clean_nans({"score": 82.5, "count": 3}) == {"score": 82.5, "count": 3}

    def test_recurses_into_nested_lists_and_dicts(self):
        data = {"points": [{"score": float("nan"), "salary": 50000}, {"score": 71.0}]}
        cleaned = _clean_nans(data)
        assert cleaned["points"][0]["score"] is None
        assert cleaned["points"][0]["salary"] == 50000
        assert cleaned["points"][1]["score"] == 71.0

    def test_leaves_strings_and_none_untouched(self):
        assert _clean_nans({"tier": "gold", "missing": None}) == {"tier": "gold", "missing": None}


def _walk_for_nan(value, path: str = "$") -> list[str]:
    """Return the JSON-path of every NaN/Infinity float found in a nested structure."""
    bad: list[str] = []
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        bad.append(path)
    elif isinstance(value, dict):
        for k, v in value.items():
            bad.extend(_walk_for_nan(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            bad.extend(_walk_for_nan(v, f"{path}[{i}]"))
    return bad


@pytest.mark.skipif(not STORY_JSON_PATH.exists(), reason="story.json not generated — run viz/story/build_story_data.py first")
class TestStoryJsonStructure:
    @pytest.fixture
    def story(self):
        with open(STORY_JSON_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_has_all_expected_top_level_step_keys(self, story):
        assert EXPECTED_TOP_LEVEL_KEYS.issubset(story.keys())

    @pytest.mark.parametrize("step", sorted(EXPECTED_KEYS_BY_STEP))
    def test_step_has_its_expected_keys(self, story, step):
        assert EXPECTED_KEYS_BY_STEP[step].issubset(story[step].keys())

    def test_no_nan_or_infinity_anywhere_in_the_output(self, story):
        assert _walk_for_nan(story) == []

    def test_funnel_stages_are_monotonically_non_increasing(self, story):
        values = [stage["value"] for stage in story["funnel"]["stages"]]
        assert values == sorted(values, reverse=True), "a funnel stage grew, which isn't a funnel"

    def test_tier_counts_sum_to_scored_total(self, story):
        tier_sum = sum(t["count"] for t in story["funnel"]["tiers"])
        scored_total = story["funnel"]["stages"][-1]["value"]
        assert tier_sum == scored_total

    def test_salary_score_point_count_matches_n(self, story):
        assert len(story["salary_score"]["points"]) == story["salary_score"]["n"]

    def test_skills_series_all_same_length_as_weeks(self, story):
        n_weeks = len(story["skills"]["weeks"])
        for skill, counts in story["skills"]["series"].items():
            assert len(counts) == n_weeks, f"{skill} series length mismatch"
