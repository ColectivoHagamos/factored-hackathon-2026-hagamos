"""Learned classifier against the keyword baseline on the held-out family of phrases (P42).

Both read the same test phrases, which no fit or choice ever saw. The report covers what the challenge asks of a
learned component: F1 per class and language, the confusion matrix, calibration (ECE), the operating point of the
POL-14 threshold, the curve on validation, the leakage check and the errors.

Usage: python -m ml.evaluate_claims   (writes docs/ml/claims_report.json)
"""

import json
from collections.abc import Callable
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from ml.claims import TEST, TRAIN, VALIDATION, ClaimClassifier, Phrase, fold, load, train
from vera.contracts.interpretation import ClaimType
from vera.llm.rules_adapter import RulesInterpreter
from vera.policy.model import load_policy

REPORT = Path(__file__).resolve().parents[1] / "docs" / "ml" / "claims_report.json"
LABELS = [claim.value for claim in ClaimType]
THRESHOLD = load_policy().parameters.interpreter_min_confidence

Predictor = Callable[[Phrase], tuple[str, float]]


def baseline() -> Predictor:
    rules = RulesInterpreter()

    def predict(phrase: Phrase) -> tuple[str, float]:
        reading = rules.interpret(phrase.text, {"language": phrase.language, "expecting": "claim"})
        return reading.claim_type.value, reading.confidence

    return predict


def learned(classifier: ClaimClassifier) -> Predictor:
    def predict(phrase: Phrase) -> tuple[str, float]:
        claim, probability = classifier.predict(phrase.text)
        return claim.value, probability

    return predict


def expected_calibration_error(confidences: list[float], correct: list[bool], bins: int = 10) -> float:
    total, error = len(confidences), 0.0
    for low in (i / bins for i in range(bins)):
        members = [i for i, c in enumerate(confidences) if low < c <= low + 1 / bins or (low == 0 and c == 0)]
        if members:
            gap = sum(correct[i] for i in members) / len(members) - sum(confidences[i] for i in members) / len(members)
            error += len(members) / total * abs(gap)
    return round(error, 4)


def scores(predict: Predictor, phrases: list[Phrase]) -> dict:
    predicted = [predict(p) for p in phrases]
    truth = [p.claim.value for p in phrases]
    labels = [claim for claim, _ in predicted]
    confidences = [confidence for _, confidence in predicted]
    correct = [label == expected for label, expected in zip(labels, truth, strict=True)]
    acted = [c >= THRESHOLD for c in confidences]
    precision, recall, f1, support = precision_recall_fscore_support(truth, labels, labels=LABELS, zero_division=0)
    by_language = {}
    for language in sorted({p.language for p in phrases}):
        index = [i for i, p in enumerate(phrases) if p.language == language]
        by_language[language] = {
            "n": len(index),
            "accuracy": round(sum(correct[i] for i in index) / len(index), 4),
            "macro_f1": round(f1_score([truth[i] for i in index], [labels[i] for i in index], average="macro"), 4),
        }
    return {
        "n": len(phrases),
        "accuracy": round(sum(correct) / len(phrases), 4),
        "macro_f1": round(f1_score(truth, labels, average="macro"), 4),
        "per_class": {
            label: {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "support": int(s)}
            for label, p, r, f, s in zip(LABELS, precision, recall, f1, support, strict=True)
        },
        "per_language": by_language,
        "confusion_matrix": {
            "labels": LABELS,
            "rows_are_truth": confusion_matrix(truth, labels, labels=LABELS).tolist(),
        },
        "ece": expected_calibration_error(confidences, correct),
        # POL-14: below the threshold VERA asks instead of acting, so what matters is acting on a wrong reading.
        "at_policy_threshold": {
            "threshold": THRESHOLD,
            "acts": round(sum(acted) / len(phrases), 4),
            "accuracy_when_acting": round(
                sum(c for c, a in zip(correct, acted, strict=True) if a) / max(1, sum(acted)), 4
            ),
            "acts_on_a_wrong_reading": round(
                sum(a and not c for c, a in zip(correct, acted, strict=True)) / len(phrases), 4
            ),
        },
        "errors": [
            {"text": p.text, "language": p.language, "truth": t, "predicted": label, "confidence": round(c, 3)}
            for p, t, label, c, ok in zip(phrases, truth, labels, confidences, correct, strict=True)
            if not ok
        ],
    }


def validation_curve(phrases: tuple[Phrase, ...]) -> list[dict]:
    """Coverage and accuracy by threshold on the validation family, fitting on the training family only."""
    fitted = train(phrases, families=(TRAIN,))
    validation = [p for p in phrases if p.family == VALIDATION]
    predicted = [fitted.predict(p.text) for p in validation]
    curve = []
    for threshold in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        acted = [
            (claim.value == p.claim.value)
            for (claim, c), p in zip(predicted, validation, strict=True)
            if c >= threshold
        ]
        curve.append(
            {
                "threshold": threshold,
                "acts": round(len(acted) / len(validation), 4),
                "accuracy_when_acting": round(sum(acted) / max(1, len(acted)), 4),
            }
        )
    return curve


def leakage(phrases: tuple[Phrase, ...]) -> dict:
    """Exact and near duplicates between the test family and the others, on folded text."""
    seen = [p for p in phrases if p.family != TEST]
    test = [p for p in phrases if p.family == TEST]

    def grams(text: str) -> set[str]:
        folded = f" {fold(text)} "
        return {folded[i : i + 5] for i in range(len(folded) - 4)}

    seen_grams = [grams(p.text) for p in seen]
    highest = 0.0
    for phrase in test:
        own = grams(phrase.text)
        for other in seen_grams:
            highest = max(highest, len(own & other) / len(own | other))
    exact = {fold(p.text) for p in test} & {fold(p.text) for p in seen}
    return {"exact_duplicates": len(exact), "highest_char5_jaccard": round(highest, 4)}


def report() -> dict:
    phrases = load()
    classifier = train(phrases)
    test = [p for p in phrases if p.family == TEST]
    return {
        "task": "claim type of the opening message, Spanish and Portuguese",
        "data": {
            family: {"phrases": sum(p.family == family for p in phrases), "role": role}
            for family, role in ((TRAIN, "train"), (VALIDATION, "validation"), (TEST, "test"))
        },
        "model": {
            "features": "TF-IDF words 1-2 and characters 2-5 on folded text",
            "classifier": "logistic regression with temperature scaling",
            "regularization_c": classifier.c,
            "temperature": classifier.temperature,
            "trained_on": list(classifier.families),
        },
        "leakage": leakage(phrases),
        "validation_curve": validation_curve(phrases),
        "test": {
            "baseline_keywords": scores(baseline(), test),
            "learned_classifier": scores(learned(classifier), test),
        },
    }


def main() -> None:
    result = report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, value in result["test"].items():
        policy = value["at_policy_threshold"]
        print(
            f"{name:20} accuracy {value['accuracy']:.3f}  macro F1 {value['macro_f1']:.3f}  ECE {value['ece']:.3f}  "
            f"acts {policy['acts']:.3f}  accuracy when acting {policy['accuracy_when_acting']:.3f}  "
            f"acts on a wrong reading {policy['acts_on_a_wrong_reading']:.3f}"
        )
    print("leakage:", result["leakage"])
    print(f"Report: {REPORT.relative_to(REPORT.parents[2])}")


if __name__ == "__main__":
    main()
