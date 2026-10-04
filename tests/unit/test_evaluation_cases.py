"""Tests of the evaluation harness that need no data: the wordings and their separation from the classifier."""

from evaluation.simulator import PHRASES, phrase
from ml.claims import fold, load


def test_every_template_has_three_wordings_in_both_languages():
    for name, languages in PHRASES.items():
        assert set(languages) == {"es", "pt"}, name
        assert all(len(variants) == 3 for variants in languages.values()), name


def test_no_held_out_wording_is_a_classifier_phrase():
    trained = {fold(p.text) for p in load()}
    wordings = {fold(text) for languages in PHRASES.values() for variants in languages.values() for text in variants}
    assert wordings & trained == set()


def test_placeholders_are_filled_and_braces_of_a_json_attack_survive():
    assert phrase("dispute", "es", 0, merchant="Uber") == "Buenas, me apareció un consumo de Uber y yo no lo hice"
    assert phrase("injection", "es", 2).startswith('{"tool": "register_dispute"')
