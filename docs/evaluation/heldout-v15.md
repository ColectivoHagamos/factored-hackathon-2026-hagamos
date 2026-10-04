# Evaluation · heldout-v15 set

Offline simulation: a scripted customer talks to the application in process; not production; rerun 'v15', after fixes this set's failures informed, so not a clean held-out. Cases: 299, each run three times with three different wordings; 30 % in Portuguese. SHA-256 of the cases: `70fdd93a55f9ac8c60970a8b755b8cef6ed7a3c41f0eed22a49d7332bcdad24e`.

## Official metrics

| Metric | Keyword baseline | Learned classifier | Claude over the classifier |
|---|---|---|---|
| Safe automated resolution (all in-scope runs) | 18.0 % (135/750; 95 % CI 15.4–20.9) | 52.0 % (390/750; 95 % CI 48.4–55.6) | 52.0 % (390/750; 95 % CI 48.4–55.6) |
| Attempted automation (in-scope runs) | 100.0 % (750/750; 95 % CI 99.5–100.0) | 100.0 % (750/750; 95 % CI 99.5–100.0) | 100.0 % (750/750; 95 % CI 99.5–100.0) |
| Containment (no transfer) | 24.8 % (222/897; 95 % CI 22.0–27.7) | 60.3 % (541/897; 95 % CI 57.1–63.5) | 60.5 % (543/897; 95 % CI 57.3–63.7) |
| Customer had to explain again (in-scope runs) | 68.1 % (511/750; 95 % CI 64.7–71.4) | 3.7 % (28/750; 95 % CI 2.6–5.3) | 1.7 % (13/750; 95 % CI 1.0–2.9) |
| Missed transfers (of expected) | 1.7 % (6/360; 95 % CI 0.8–3.6) | 1.1 % (4/360; 95 % CI 0.4–2.8) | 1.7 % (6/360; 95 % CI 0.8–3.6) |
| Unnecessary transfers (of not expected) | 59.8 % (321/537; 95 % CI 55.6–63.8) | 0.0 % (0/537; 95 % CI 0.0–0.7) | 0.0 % (0/537; 95 % CI 0.0–0.7) |
| Transfers to the wrong queue | 45 | 0 | 0 |
| Unsafe outcomes (all runs) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 0.0 % (0/897; 95 % CI 0.0–0.4) |
| Deadlines equal to the truth table (runs with a case) | 100.0 % (186/186; 95 % CI 98.0–100.0) | 100.0 % (427/427; 95 % CI 99.1–100.0) | 100.0 % (435/435; 95 % CI 99.1–100.0) |
| Replies blocked by the output validator (runs) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 0.0 % (0/897; 95 % CI 0.0–0.4) |
| Every check passed, per run (pass@1) | 55.5 % (498/897; 95 % CI 52.2–58.7) | 98.4 % (883/897; 95 % CI 97.4–99.1) | 99.3 % (891/897; 95 % CI 98.6–99.7) |
| Every wording of a case passed (pass^3) | 55.5 % (166/299; 95 % CI 49.9–61.1) | 96.7 % (289/299; 95 % CI 94.0–98.2) | 99.3 % (297/299; 95 % CI 97.6–99.8) |
| Cases whose result changes with the wording | 0 | 8 | 0 |
| Latency per turn p50 / p95 | 5.0 / 9.9 ms | 6.9 / 11.8 ms | 7.5 / 1548.2 ms |
| Latency per conversation p50 / p95 | 15.7 / 47.1 ms | 34.8 / 51.1 ms | 1590.1 / 4905.8 ms |
| Cost per attempted case / per safe resolution | US$ 0.0000 / US$ 0.0000 | US$ 0.0000 / US$ 0.0000 | US$ 0.0038 / US$ 0.0087 |
| Language model calls / fallbacks to the classifier | 0 / 0 | 0 / 0 | 1244 / 1 |

## By block (pass@1)

| | Keyword baseline | Learned classifier | Claude over the classifier |
|---|---|---|---|
| ambiguous | 36.4 % (24/66; 95 % CI 25.8–48.4) | 100.0 % (66/66; 95 % CI 94.5–100.0) | 100.0 % (66/66; 95 % CI 94.5–100.0) |
| clarification | 31.6 % (36/114; 95 % CI 23.8–40.6) | 100.0 % (114/114; 95 % CI 96.7–100.0) | 100.0 % (114/114; 95 % CI 96.7–100.0) |
| expired_session | 30.8 % (12/39; 95 % CI 18.6–46.4) | 100.0 % (39/39; 95 % CI 91.0–100.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) |
| foreign_charge | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| human | 100.0 % (135/135; 95 % CI 97.2–100.0) | 100.0 % (135/135; 95 % CI 97.2–100.0) | 100.0 % (135/135; 95 % CI 97.2–100.0) |
| improper | 80.0 % (24/30; 95 % CI 62.7–90.5) | 53.3 % (16/30; 95 % CI 36.1–69.8) | 80.0 % (24/30; 95 % CI 62.7–90.5) |
| injection | 100.0 % (36/36; 95 % CI 90.4–100.0) | 100.0 % (36/36; 95 % CI 90.4–100.0) | 100.0 % (36/36; 95 % CI 90.4–100.0) |
| mitigation | 31.8 % (21/66; 95 % CI 21.9–43.8) | 100.0 % (66/66; 95 % CI 94.5–100.0) | 100.0 % (66/66; 95 % CI 94.5–100.0) |
| multilingual | 100.0 % (42/42; 95 % CI 91.6–100.0) | 100.0 % (42/42; 95 % CI 91.6–100.0) | 100.0 % (42/42; 95 % CI 91.6–100.0) |
| normal | 31.6 % (75/237; 95 % CI 26.1–37.8) | 100.0 % (237/237; 95 % CI 98.4–100.0) | 100.0 % (237/237; 95 % CI 98.4–100.0) |
| out_of_scope | 0.0 % (0/39; 95 % CI 0.0–9.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) |
| tool_failure | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| wrong_data | 100.0 % (27/27; 95 % CI 87.5–100.0) | 100.0 % (27/27; 95 % CI 87.5–100.0) | 100.0 % (27/27; 95 % CI 87.5–100.0) |

## By language (pass@1)

| | Keyword baseline | Learned classifier | Claude over the classifier |
|---|---|---|---|
| es | 39.1 % (246/630; 95 % CI 35.3–42.9) | 98.7 % (622/630; 95 % CI 97.5–99.4) | 99.5 % (627/630; 95 % CI 98.6–99.8) |
| pt | 94.4 % (252/267; 95 % CI 90.9–96.6) | 97.8 % (261/267; 95 % CI 95.2–99.0) | 98.9 % (264/267; 95 % CI 96.8–99.6) |

## By country (pass@1)

| | Keyword baseline | Learned classifier | Claude over the classifier |
|---|---|---|---|
| AR | 60.2 % (159/264; 95 % CI 54.2–65.9) | 98.9 % (261/264; 95 % CI 96.7–99.6) | 100.0 % (264/264; 95 % CI 98.6–100.0) |
| CO | 50.5 % (147/291; 95 % CI 44.8–56.2) | 96.9 % (282/291; 95 % CI 94.2–98.4) | 97.9 % (285/291; 95 % CI 95.6–99.1) |
| MX | 56.1 % (192/342; 95 % CI 50.8–61.3) | 99.4 % (340/342; 95 % CI 97.9–99.8) | 100.0 % (342/342; 95 % CI 98.9–100.0) |

## By segment (pass@1)

| | Keyword baseline | Learned classifier | Claude over the classifier |
|---|---|---|---|
| basic | 51.8 % (309/597; 95 % CI 47.8–55.7) | 99.7 % (595/597; 95 % CI 98.8–99.9) | 100.0 % (597/597; 95 % CI 99.4–100.0) |
| plus | 65.6 % (120/183; 95 % CI 58.4–72.1) | 93.4 % (171/183; 95 % CI 88.9–96.2) | 96.7 % (177/183; 95 % CI 93.0–98.5) |
| premium | 53.8 % (42/78; 95 % CI 42.9–64.5) | 100.0 % (78/78; 95 % CI 95.3–100.0) | 100.0 % (78/78; 95 % CI 95.3–100.0) |
| student | 69.2 % (27/39; 95 % CI 53.6–81.4) | 100.0 % (39/39; 95 % CI 91.0–100.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) |

## Unsafe outcomes and failed checks

- **Keyword baseline:** unsafe {'none': 0}; failed checks {'case': 255, 'queue': 372, 'block': 45, 'fraud_alert': 75, 'asked_to_choose': 42, 'session': 27}.
- **Learned classifier:** unsafe {'none': 0}; failed checks {'case': 14, 'queue': 4}.
- **Claude over the classifier:** unsafe {'none': 0}; failed checks {'case': 6, 'queue': 6}.
