# Evaluation · heldout-after set

Offline simulation: a scripted customer talks to the application in process; not production; rerun 'after', after fixes this set's failures informed, so not a clean held-out. Cases: 299, each run three times with three different wordings; 30 % in Portuguese. SHA-256 of the cases: `70fdd93a55f9ac8c60970a8b755b8cef6ed7a3c41f0eed22a49d7332bcdad24e`.

## Official metrics

| Metric | Keyword baseline | Learned classifier |
|---|---|---|
| Safe automated resolution (all in-scope runs) | 18.0 % (135/750; 95 % CI 15.4–20.9) | 52.0 % (390/750; 95 % CI 48.4–55.6) |
| Attempted automation (in-scope runs) | 35.5 % (266/750; 95 % CI 32.1–39.0) | 90.8 % (681/750; 95 % CI 88.5–92.7) |
| Containment (no transfer) | 24.8 % (222/897; 95 % CI 22.0–27.7) | 60.2 % (540/897; 95 % CI 57.0–63.3) |
| Customer had to explain again (in-scope runs) | 68.1 % (511/750; 95 % CI 64.7–71.4) | 2.9 % (22/750; 95 % CI 1.9–4.4) |
| Missed transfers (of expected) | 1.7 % (6/360; 95 % CI 0.8–3.6) | 0.8 % (3/360; 95 % CI 0.3–2.4) |
| Unnecessary transfers (of not expected) | 59.8 % (321/537; 95 % CI 55.6–63.8) | 0.0 % (0/537; 95 % CI 0.0–0.7) |
| Transfers to the wrong queue | 45 | 0 |
| Unsafe outcomes (all runs) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 0.0 % (0/897; 95 % CI 0.0–0.4) |
| Every check passed, per run (pass@1) | 55.5 % (498/897; 95 % CI 52.2–58.7) | 97.9 % (878/897; 95 % CI 96.7–98.6) |
| Every wording of a case passed (pass^3) | 55.5 % (166/299; 95 % CI 49.9–61.1) | 96.7 % (289/299; 95 % CI 94.0–98.2) |
| Cases whose result changes with the wording | 0 | 8 |
| Latency per turn p50 / p95 | 4.3 / 10.0 ms | 6.7 / 13.1 ms |
| Latency per conversation p50 / p95 | 13.5 / 45.4 ms | 34.8 / 51.7 ms |
| Cost per attempted case / per safe resolution | US$ 0.00 / 0.0 | US$ 0.00 / 0.0 |

## By block (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| ambiguous | 36.4 % (24/66; 95 % CI 25.8–48.4) | 100.0 % (66/66; 95 % CI 94.5–100.0) |
| clarification | 31.6 % (36/114; 95 % CI 23.8–40.6) | 100.0 % (114/114; 95 % CI 96.7–100.0) |
| expired_session | 30.8 % (12/39; 95 % CI 18.6–46.4) | 100.0 % (39/39; 95 % CI 91.0–100.0) |
| foreign_charge | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| human | 100.0 % (135/135; 95 % CI 97.2–100.0) | 100.0 % (135/135; 95 % CI 97.2–100.0) |
| improper | 80.0 % (24/30; 95 % CI 62.7–90.5) | 36.7 % (11/30; 95 % CI 21.9–54.5) |
| injection | 100.0 % (36/36; 95 % CI 90.4–100.0) | 100.0 % (36/36; 95 % CI 90.4–100.0) |
| mitigation | 31.8 % (21/66; 95 % CI 21.9–43.8) | 100.0 % (66/66; 95 % CI 94.5–100.0) |
| multilingual | 100.0 % (42/42; 95 % CI 91.6–100.0) | 100.0 % (42/42; 95 % CI 91.6–100.0) |
| normal | 31.6 % (75/237; 95 % CI 26.1–37.8) | 100.0 % (237/237; 95 % CI 98.4–100.0) |
| out_of_scope | 0.0 % (0/39; 95 % CI 0.0–9.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) |
| tool_failure | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| wrong_data | 100.0 % (27/27; 95 % CI 87.5–100.0) | 100.0 % (27/27; 95 % CI 87.5–100.0) |

## By language (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| es | 39.1 % (246/630; 95 % CI 35.3–42.9) | 97.9 % (617/630; 95 % CI 96.5–98.8) |
| pt | 94.4 % (252/267; 95 % CI 90.9–96.6) | 97.8 % (261/267; 95 % CI 95.2–99.0) |

## By country (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| AR | 60.2 % (159/264; 95 % CI 54.2–65.9) | 98.1 % (259/264; 95 % CI 95.6–99.2) |
| CO | 50.5 % (147/291; 95 % CI 44.8–56.2) | 96.2 % (280/291; 95 % CI 93.4–97.9) |
| MX | 56.1 % (192/342; 95 % CI 50.8–61.3) | 99.1 % (339/342; 95 % CI 97.5–99.7) |

## By segment (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| basic | 51.8 % (309/597; 95 % CI 47.8–55.7) | 99.3 % (593/597; 95 % CI 98.3–99.7) |
| plus | 65.6 % (120/183; 95 % CI 58.4–72.1) | 91.8 % (168/183; 95 % CI 86.9–95.0) |
| premium | 53.8 % (42/78; 95 % CI 42.9–64.5) | 100.0 % (78/78; 95 % CI 95.3–100.0) |
| student | 69.2 % (27/39; 95 % CI 53.6–81.4) | 100.0 % (39/39; 95 % CI 91.0–100.0) |

## Unsafe outcomes and failed checks

- **Keyword baseline:** unsafe {'none': 0}; failed checks {'case': 255, 'queue': 372, 'block': 45, 'fraud_alert': 75, 'asked_to_choose': 42, 'session': 27}.
- **Learned classifier:** unsafe {'none': 0}; failed checks {'case': 19, 'queue': 3}.
