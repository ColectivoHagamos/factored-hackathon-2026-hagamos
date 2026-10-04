# Model card · claim classifier

The learned component of VERA (plan step P42). It reads the customer's first message and says what kind of claim it is, so the conversation takes the right path. It is compared against the keyword patterns of the rules interpreter, the baseline, on phrases that no fit or choice ever saw. Every number below comes from `docs/ml/claims_report.json`, which `make ml-report` regenerates.

## What it does and what it does not

| | |
|---|---|
| **Input** | The masked text of the opening message, in Spanish or Portuguese |
| **Output** | One of five claim types and its calibrated probability: `unrecognized_charge`, `improper_charge`, `scam_transfer`, `human_request`, `out_of_scope` |
| **Used for** | The opening claim only (`VERA_LLM=classifier`). Answers, option numbers, amounts, merchants, channel, card possession and the safety words (a person, coercion, regulator, Pix) stay with the deterministic rules |
| **Decides nothing** | The probability is the confidence that POL-14 reads: below 0.6 VERA asks instead of acting. A wrong reading can only take the conversation down the wrong path; every action still needs the customer's confirmation and the action gate |
| **Model** | TF-IDF of words (1-2) and characters (2-5) on lower-cased text without accents, and a logistic regression with balanced class weights; probabilities sharpened by temperature scaling |
| **Size and cost** | Retrained from the versioned phrases in under a second when the service starts; no model file is versioned (a pickle is a supply-chain risk, LLM03). US$ 0 per message |

## Data

The team wrote 329 phrases for this purpose: five classes, in Spanish and Portuguese (`ml/phrases/claims.yaml`).

- **No phrase comes from the dataset.** Balance and other out-of-scope questions are our own paraphrases.
- **Three families with no shared template,** so the split is by template rather than at random, and nothing leaks into the test:

| Family | Phrases | Style | Role |
|---|---:|---|---|
| a | 121 | Complete sentences, neutral register | Training |
| b | 120 | Chat style: short, without accents, typos, *voseo* | Validation: regularization and temperature |
| c | 88 | Other wordings, longer stories and hard cases ("una comisión por consultar el saldo", "Transfiérame con su supervisor") | Test only |

- **Leakage check:** no test phrase repeats a training or validation phrase after folding, and the highest character 5-gram Jaccard similarity between a test phrase and any other is 0.47.
- **Choices made on validation:**
  - the regularization (C = 2.0), by the best macro F1 of a model fitted on family a;
  - the temperature (0.25), by the lowest log loss.
  - The final model is fitted on families a and b.

## Results on the test family (88 phrases)

| | Accuracy | Macro F1 | ECE | Acts (confidence ≥ 0.6) | Accuracy when it acts | Acts on a wrong reading |
|---|---:|---:|---:|---:|---:|---:|
| Keyword baseline | 0.455 | 0.425 | 0.124 | 31.8 % | 92.9 % | 2.3 % |
| **Learned classifier** | **0.875** | **0.880** | **0.062** | **87.5 %** | **96.1 %** | **3.4 %** |

"Acts" is the share of messages the conversation follows without asking again, which is what the threshold of POL-14 decides. The baseline acts rarely because a keyword pattern either matches exactly or the rules return a low confidence, so VERA asks.

**The baseline numbers are optimistic.** On 4 October, after the held-out evaluation, the keyword patterns for a request for a person were extended ("hablar con alguien", "supervisor", "atención al cliente", "carne y hueso"). Some of those expressions also appear in this test family, which the baseline had never been tuned on before; its accuracy rose from 0.330 to 0.432. Later that day, the rules stopped reading a role inside a scam story ("un supuesto asesor del banco") as a request for a person, and it rose to 0.455. The learned classifier did not change.

**Acting less is not acting better.** The baseline now acts on a wrong reading in 2 of 88 messages and the classifier in 3, but the baseline acts on a third of the messages and the classifier on seven in eight. When it acts, the classifier is right more often (96.1 % against 92.9 %): it asks less and errs less per decision. The share of wrong actions is kept under 5 % by a test.

**By class (learned classifier, F1):**

| Class | F1 |
|---|---:|
| `scam_transfer` | 1.000 |
| `human_request` | 0.970 |
| `out_of_scope` | 0.813 |
| `improper_charge` | 0.811 |
| `unrecognized_charge` | 0.810 |

**By language:**

| Language | Phrases | Accuracy | Macro F1 |
|---|---:|---:|---:|
| Spanish | 44 | 0.932 | 0.935 |
| Portuguese | 44 | 0.818 | 0.826 |

Portuguese is weaker. Its phrases repeat fewer distinct expressions, and "cobrança" appears in both unrecognized and improper charges.

**The threshold.** The 0.6 of POL-14 is a policy parameter, so this card reports how the classifier behaves at it; it does not change it. On validation, 0.7 would act on 86 % of messages with 98 % accuracy, against 89 % and 95 % at 0.6 (`validation_curve` in the report).

## Errors

Three test phrases are read wrongly with a confidence of 0.6 or more, so VERA would follow the wrong path:

| Phrase | Truth | Read as |
|---|---|---|
| La compra salió repetida tres veces en el estado de cuenta | improper charge | unrecognized charge (0.76) |
| ¿Qué requisitos piden para una tarjeta de crédito? | out of scope | unrecognized charge (0.74) |
| Não sei o que é essa cobrança do PayPal | unrecognized charge | improper charge (0.81) |

- **In the first two,** the card and purchase vocabulary pulls the message toward the most common class, and the duplicate is described without "doble" or "cobro".
- **The other eight errors** have a confidence below 0.6, so VERA asks again instead of acting on them.
- **The errors were not added to the training data:** that would tune the model to its own test.

## Limits and honest caveats

- **One team wrote all three families.** Splitting by template prevents phrase-level leakage, but a shared style can still make the test easier than real messages.
- **The human blind set** (plan step P25), written by people who did not write these phrases, is the real test of language variety. Its result will be reported separately when it exists.
- **The test family is small** (88 phrases, 8 to 10 per class and language), so a difference of one phrase moves accuracy by more than one point.
- **Only the five claim types of the design.** A message that mixes two claims gets one label; the conversation then asks for the charge, so a mixed claim is clarified there.
- **No production data** was used or exists; the deployed demo uses the pseudonymized demo subset of the synthetic dataset.

## How to reproduce

```bash
make ml-report   # retrains the classifier and writes docs/ml/claims_report.json
```

The tests in `tests/unit/test_claim_classifier.py` check the families, the leakage, the determinism of the training, and that the versioned report matches a fresh run.
