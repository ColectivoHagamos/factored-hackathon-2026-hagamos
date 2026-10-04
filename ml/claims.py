"""Learned claim classifier (P42): TF-IDF of words and characters with a logistic regression, in Spanish and Portuguese.

It is the learned component the challenge asks to compare against a baseline (the keyword patterns of the rules
interpreter). It retrains from ml/phrases/claims.yaml in about a second, so no model file is versioned (LLM03).
Family "a" trains, family "b" chooses the regularization, and family "c" is only read by the evaluation.
"""

import math
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import FeatureUnion, Pipeline
from threadpoolctl import threadpool_limits

from vera.contracts.interpretation import ClaimType

DATA = Path(__file__).parent / "phrases" / "claims.yaml"
TRAIN, VALIDATION, TEST = "a", "b", "c"
C_GRID = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
TEMPERATURES = tuple(round(0.05 * step, 2) for step in range(2, 41))


@dataclass(frozen=True)
class Phrase:
    text: str
    claim: ClaimType
    language: str
    family: str


def fold(text: str) -> str:
    """Lower case without accents, so "no reconozco" and "No reconozcó" read the same."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def load(path: Path = DATA) -> tuple[Phrase, ...]:
    families = yaml.safe_load(path.read_text(encoding="utf-8"))["families"]
    return tuple(
        Phrase(text=text, claim=ClaimType(claim), language=language, family=family)
        for family, languages in families.items()
        for language, claims in languages.items()
        for claim, texts in claims.items()
        for text in texts
    )


def pipeline(c: float) -> Pipeline:
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(preprocessor=fold, ngram_range=(1, 2), sublinear_tf=True)),
            ("chars", TfidfVectorizer(preprocessor=fold, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ]
    )
    model = LogisticRegression(C=c, class_weight="balanced", max_iter=5000)
    return Pipeline([("features", features), ("model", model)])


def choose_c(phrases: tuple[Phrase, ...]) -> float:
    """The regularization with the best macro F1 on the validation family, after fitting on the training family."""
    train = [p for p in phrases if p.family == TRAIN]
    validation = [p for p in phrases if p.family == VALIDATION]
    scores = {}
    for c in C_GRID:
        fitted = pipeline(c).fit([p.text for p in train], [p.claim.value for p in train])
        predicted = fitted.predict([p.text for p in validation])
        scores[c] = f1_score([p.claim.value for p in validation], predicted, average="macro")
    return max(C_GRID, key=lambda c: (scores[c], -c))


def softmax(scores: list[float], temperature: float) -> list[float]:
    scaled = [score / temperature for score in scores]
    top = max(scaled)
    exps = [math.exp(score - top) for score in scaled]
    total = sum(exps)
    return [value / total for value in exps]


def choose_temperature(phrases: tuple[Phrase, ...], c: float) -> float:
    """Temperature scaling: the one that minimizes the log loss on validation, after fitting on the training family.

    Logistic regression on a few hundred phrases spreads its probability over five classes and comes out
    underconfident; a temperature below one sharpens it without changing which class wins.
    """
    train = [p for p in phrases if p.family == TRAIN]
    validation = [p for p in phrases if p.family == VALIDATION]
    fitted = pipeline(c).fit([p.text for p in train], [p.claim.value for p in train])
    classes = list(fitted.classes_)
    scores = fitted.decision_function([p.text for p in validation]).tolist()
    truth = [classes.index(p.claim.value) for p in validation]

    def log_loss(temperature: float) -> float:
        return -sum(math.log(softmax(row, temperature)[t]) for row, t in zip(scores, truth, strict=True))

    return min(TEMPERATURES, key=log_loss)


class ClaimClassifier:
    """Predicts the claim type and its calibrated probability, which is the confidence that POL-14 reads."""

    def __init__(self, fitted: Pipeline, c: float, temperature: float, families: tuple[str, ...]) -> None:
        self._fitted = fitted
        self.c = c
        self.temperature = temperature
        self.families = families

    def predict(self, text: str) -> tuple[ClaimType, float]:
        probabilities = softmax(self._fitted.decision_function([text])[0].tolist(), self.temperature)
        best = max(range(len(probabilities)), key=probabilities.__getitem__)
        return ClaimType(self._fitted.classes_[best]), probabilities[best]


def train(phrases: tuple[Phrase, ...], families: tuple[str, ...] = (TRAIN, VALIDATION)) -> ClaimClassifier:
    """Fit on the given families with the regularization chosen on validation; the test family is never used."""
    if TEST in families:
        raise ValueError("the test family is only for evaluation")
    # With a few hundred phrases, one BLAS thread fits in a fraction of a second; many threads take seconds.
    with threadpool_limits(limits=1):
        c = choose_c(phrases)
        temperature = choose_temperature(phrases, c)
        used = [p for p in phrases if p.family in families]
        fitted = pipeline(c).fit([p.text for p in used], [p.claim.value for p in used])
    return ClaimClassifier(fitted, c, temperature, families)


@cache
def default_classifier() -> ClaimClassifier:
    """The classifier the service uses, trained once per process from the versioned phrases."""
    return train(load())
