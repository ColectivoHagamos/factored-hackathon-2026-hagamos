"""Tests of the learned claim classifier (P42): data families, leakage, determinism and the versioned report."""

import json
from collections import Counter

import pytest

from ml.claims import TEST, ClaimClassifier, fold, load, train
from ml.evaluate_claims import REPORT, report
from vera.contracts.interpretation import ClaimType
from vera.llm.classifier_adapter import ClassifierInterpreter

PHRASES = load()


@pytest.fixture(scope="module")
def classifier() -> ClaimClassifier:
    return train(PHRASES)


@pytest.fixture(scope="module")
def fresh_report() -> dict:
    return report()


def test_every_family_has_every_class_in_both_languages():
    cells = Counter((p.family, p.language, p.claim) for p in PHRASES)
    for family in ("a", "b", "c"):
        for language in ("es", "pt"):
            assert all(cells[(family, language, claim)] >= 8 for claim in ClaimType)


def test_no_phrase_repeats_across_families():
    by_text = Counter(fold(p.text) for p in PHRASES)
    assert [text for text, count in by_text.items() if count > 1] == []


def test_the_test_family_is_never_used_to_train():
    with pytest.raises(ValueError, match="test family"):
        train(PHRASES, families=("a", TEST))


def test_training_is_deterministic(classifier: ClaimClassifier):
    again = train(PHRASES)
    texts = [p.text for p in PHRASES if p.family == TEST]
    assert [classifier.predict(t) for t in texts] == [again.predict(t) for t in texts]


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("No reconozco un cargo de Uber", ClaimType.UNRECOGNIZED_CHARGE),
        ("Me cobraron dos veces la misma compra", ClaimType.IMPROPER_CHARGE),
        ("Me estafaron y transferí dinero", ClaimType.SCAM_TRANSFER),
        ("Quero falar com uma pessoa", ClaimType.HUMAN_REQUEST),
        ("¿Cuál es mi saldo?", ClaimType.OUT_OF_SCOPE),
    ],
)
def test_clear_messages_are_read_with_confidence(classifier: ClaimClassifier, text: str, claim: ClaimType):
    predicted, probability = classifier.predict(text)
    assert predicted is claim and probability >= 0.6


def test_the_learned_component_beats_the_baseline_on_the_test_family(fresh_report: dict):
    learned, baseline = fresh_report["test"]["learned_classifier"], fresh_report["test"]["baseline_keywords"]
    assert learned["macro_f1"] > baseline["macro_f1"]
    # The baseline acts on a third of the messages, so its share of wrong actions is small by abstaining; the fair
    # comparison is how often each one is right when it acts, plus a ceiling on wrong actions.
    learned_acting, baseline_acting = learned["at_policy_threshold"], baseline["at_policy_threshold"]
    assert learned_acting["accuracy_when_acting"] >= baseline_acting["accuracy_when_acting"]
    assert learned_acting["acts_on_a_wrong_reading"] < 0.05
    assert fresh_report["leakage"]["exact_duplicates"] == 0


def test_the_versioned_report_matches_a_fresh_run(fresh_report: dict):
    """Run make ml-report after changing the phrases or the model."""
    versioned = json.loads(REPORT.read_text(encoding="utf-8"))
    for system in ("baseline_keywords", "learned_classifier"):
        for metric in ("accuracy", "macro_f1", "ece"):
            assert versioned["test"][system][metric] == pytest.approx(fresh_report["test"][system][metric], abs=0.02)
    assert versioned["model"]["regularization_c"] == fresh_report["model"]["regularization_c"]


def test_a_plea_for_help_is_not_given_to_the_classifier():
    class Insists:
        def predict(self, text):
            return ClaimType.HUMAN_REQUEST, 0.99

    reading = ClassifierInterpreter(Insists()).interpret("Estoy desesperada, necesito ayuda", {"expecting": "claim"})
    assert reading.greeting and reading.distress and reading.claim_type is not ClaimType.HUMAN_REQUEST
