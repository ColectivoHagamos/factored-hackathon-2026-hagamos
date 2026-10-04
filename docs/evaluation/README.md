# Evaluation

How VERA is measured against a baseline on the same held-out cases, and what the measurement found. The evaluation is an **offline simulation**: a scripted customer talks to the real application in process. It is not a measurement in production, and it does not project business savings.

## Method

| | |
|---|---|
| **Systems** | The keyword baseline (rules interpreter) and the learned claim classifier (`VERA_LLM=classifier`, see the [model card](../model_card.md)). Everything else is the same: policy, flow, tools, action gate and validator |
| **Cases** | Built from the pseudonymized demo subset (`evaluation/generate.py`); a case holds only pseudonymous references. The expected final state is labeled by construction from the policy (POL-03, 05, 06, 07, 08, 11, 13), never by a run |
| **Blocks** | Normal, clarification, mitigation, ambiguous, human, improper charge, out of scope, and six attacks: injection, another customer's data, expired session, tool failure, wrong data and mixed languages |
| **Simulated customer** | Deterministic (`evaluation/simulator.py`). It only answers what VERA asks: it picks its charge on screen, says whether it has the card, accepts or declines the block and confirms. When it is not understood, it gives its merchant once, tells its claim in other words twice, and leaves. When VERA offers to review the case before a transfer (POL-01, policy v1.5), a customer who asked for a person insists and any other accepts |
| **Runs** | Every case three times, each with a different wording; pass^3 asks a case to succeed with all three |
| **Graders** | The final state is the source of truth: the charges in the case, blocks, the handoff queue, security events, fraud alerts and the session (`evaluation/graders.py`). Unsafe outcomes are graded apart from mistakes. The deadlines shown in the glass box are compared with a truth table written by hand for the simulated filing day (2026-06-18), and every reply the output validator blocked is counted. The graders have their own tests with known good and bad runs (`tests/unit/test_graders.py`) |
| **Metrics** | The official metrics of the challenge, with their denominators and 95 % Wilson intervals, by block, language, country and segment (`evaluation/report.py`) |
| **Cost** | US$ 0 per case for both systems: no paid model is called. The language model adapters are not part of this evaluation |

## Sets and sealing

| Set | Cases | Wordings | Use |
|---|---:|---|---|
| Development | 88 | `evaluation/phrases_dev.yaml` | The only set used to debug the harness and to find what to fix |
| Held-out | 299 | `evaluation/phrases_heldout.yaml` | Run once, as sealed; published as is |

- **Sealed before its first run.** The held-out cases and their wordings were committed to `development` and marked with the annotated tag `heldout-v1`.
  - sha256 of the cases: `70fdd93a55f9ac8c60970a8b755b8cef6ed7a3c41f0eed22a49d7332bcdad24e`
  - sha256 of the wordings: `c3825e51ba3edc6b980cf1316092639713e17c017da908e703c8a8ca9844ab5e`
- **Separate wordings.** The two sets and the classifier phrases share no wording; a test checks it.
- **No leakage.** The leakage audit finds no real identifier of the dataset in the cases or the wordings.
- **Shares.** 30 % of the cases are in Portuguese; 750 of the 897 runs per system are in scope.

## Held-out results, as sealed

Full report: [heldout.md](heldout.md), with the data in [heldout.json](heldout.json). Measured with policy v1.4, when a request for a person was transferred at once.

| Metric | Keyword baseline | Learned classifier |
|---|---:|---:|
| Safe automated resolution (in-scope runs) | 18.0 % | 44.5 % |
| Attempted automation | 35.5 % | 90.8 % |
| Containment | 24.8 % | 57.3 % |
| Customer had to explain again | 70.5 % | 4.3 % |
| Missed transfers | 1.7 % (6/360) | 4.7 % (17/360) |
| Unnecessary transfers | 59.8 % (321/537) | 7.4 % (40/537) |
| **Unsafe outcomes** | **0.0 % (0/897)** | **3.3 % (30/897)** |
| pass@1 / pass^3 | 55.5 % / 55.5 % | 88.6 % / 68.9 % |
| Latency per turn p50 / p95 | 4.5 / 10.5 ms | 6.6 / 14.1 ms |

The learned classifier understands far more customers. It resolves 2.5 times as many cases without a person and transfers an eighth as many without need. But it also produced **30 unsafe runs, where the baseline produced none**.

## What failed, and why

All 30 unsafe runs, and most of the classifier's other failures, share one root cause:

1. **The merchant was not extracted.**
   - The interpreter looked for the merchant only after a preposition ("un cargo **de** Uber"). In the third held-out wording ("aparece *merchant* en mis movimientos…"), it found none, so VERA searched the recent charges without a filter.
   - When one other charge was left, VERA showed it as the one in question and asked "¿Reconoce el cargo?".
   - The simulated customer, which answers that question without checking whose receipt it sees, said "no", and VERA registered a dispute for a charge the customer never named.
   - The baseline never reached that point: with no keyword, its confidence was low and it asked again. Its caution, not its understanding, kept it safe.
2. **A request for a person, missed in the middle of the flow.** "Quiero hablar con alguien del banco ya" matched no pattern. In the middle of the flow only the deterministic rules read the message, so the conversation went on. This is a POL-01 miss. The gap is in the rules both systems share, but only the classifier system got far enough in those runs to show it.
3. **Improper charges read as unrecognized ones.** The classifier read "un cargo del banco que no entiendo" as an unrecognized purchase: 16 improper-charge runs ended without a case, and safely with a person.
4. **The baseline's misreadings.**
   - In 70.5 % of in-scope runs it had to ask the customer to explain again.
   - It sent 45 runs to the wrong queue, for example a fraud case to Complaints.
   - It transferred 321 runs that needed no person.

**What these results are not:**

- **Not a production rate.** The cases are synthetic and the customer is scripted.
- **Not a measure of the language model.** It is not part of this run.
- **Not a measure of real language variety.** All wordings were written by the team; the human blind set (P25) will measure that apart.

## After the fixes

Causes 1 and 2 were fixed in #48: the merchant is now found wherever it is named, and more ways to ask for a person match. The fixes were tested with wordings of their own, never with held-out phrases. The same 299 cases and wordings were then run again. That rerun is published apart ([heldout-after.md](heldout-after.md), [heldout-after.json](heldout-after.json)) and is **not a clean held-out**, because its failures informed the fixes. The sealed numbers above remain the honest measurement.

| Learned classifier | Sealed run | After the fixes |
|---|---:|---:|
| Safe automated resolution (in-scope runs) | 44.5 % | 52.0 % |
| Containment | 57.3 % | 60.2 % |
| Customer had to explain again | 4.3 % | 2.9 % |
| Missed transfers | 17 of 360 | 3 of 360 |
| Unnecessary transfers | 40 of 537 | 0 of 537 |
| **Unsafe outcomes** | **30 of 897** | **0 of 897** |
| pass@1 / pass^3 | 88.6 % / 68.9 % | 97.9 % / 96.7 % |

- **The keyword baseline did not change** (pass@1 55.5 %, no unsafe outcome). Its failures come from not understanding the claim, which a better merchant extraction does not fix.
- **All 19 runs the classifier still fails are improper charges, cause 3.** "Un cargo del banco que no entiendo" is read as an unrecognized purchase. They fail safely: no case is registered, and in 3 of them the conversation goes to a person. Fixing it means retraining with more improper-charge phrases, which would then need a new sealed set to be measured honestly.

## Reproduce

The evaluation needs the pseudonymized demo subset, which lives outside the repository, so it does not run in CI:

```bash
export VERA_DEMO_DB=/path/to/demo.duckdb
make evaluation SET=dev        # development set
make evaluation SET=heldout    # the sealed set
```
