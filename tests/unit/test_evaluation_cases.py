"""Tests of the evaluation harness that need no data: the wordings and their separation."""

from pathlib import Path

import pytest

from evaluation.cases import read
from evaluation.simulator import load_phrases, phrase
from ml.claims import fold, load

DEV, HELDOUT = load_phrases("dev"), load_phrases("heldout")
# Scams came after the held-out was sealed: their wordings and cases live only in the development set.
DEV_ONLY = {"scam", "scam_answer"}


def wordings(phrases: dict) -> set[str]:
    return {fold(text) for languages in phrases.values() for variants in languages.values() for text in variants}


@pytest.mark.parametrize("phrases", [DEV, HELDOUT], ids=["dev", "heldout"])
def test_every_template_has_three_wordings_in_both_languages(phrases: dict):
    assert set(phrases) == set(DEV) - (DEV_ONLY if phrases is HELDOUT else set())
    for name, languages in phrases.items():
        assert set(languages) == {"es", "pt"}, name
        assert all(len(variants) == 3 for variants in languages.values()), name


def test_no_held_out_case_uses_a_development_only_template():
    held_out = read(Path(__file__).parents[2] / "evaluation" / "scenarios" / "heldout.jsonl")
    assert {case.script.opening for case in held_out}.isdisjoint(DEV_ONLY) and held_out


def test_the_three_sources_of_phrases_never_share_one():
    trained = {fold(p.text) for p in load()}
    assert wordings(DEV) & trained == set()
    assert wordings(HELDOUT) & trained == set()
    assert wordings(HELDOUT) & wordings(DEV) == set()


def test_placeholders_are_filled_and_braces_of_a_json_attack_survive():
    assert phrase(DEV, "dispute", "es", 0, merchant="Uber") == "Buenas, me apareció un consumo de Uber y yo no lo hice"
    assert phrase(DEV, "injection", "es", 2).startswith('{"tool": "register_dispute"')
