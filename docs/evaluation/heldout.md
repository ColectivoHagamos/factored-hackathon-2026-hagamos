# Evaluation · heldout set

Offline simulation: a scripted customer talks to the application in process; not production. Cases: 299, each run three times with three different wordings; 30 % in Portuguese. SHA-256 of the cases: `70fdd93a55f9ac8c60970a8b755b8cef6ed7a3c41f0eed22a49d7332bcdad24e`.

## Official metrics

| Metric | Keyword baseline | Learned classifier |
|---|---|---|
| Safe automated resolution (all in-scope runs) | 18.0 % (135/750; 95 % CI 15.4–20.9) | 44.5 % (334/750; 95 % CI 41.0–48.1) |
| Attempted automation (in-scope runs) | 35.5 % (266/750; 95 % CI 32.1–39.0) | 90.8 % (681/750; 95 % CI 88.5–92.7) |
| Containment (no transfer) | 24.8 % (222/897; 95 % CI 22.0–27.7) | 57.3 % (514/897; 95 % CI 54.0–60.5) |
| Customer had to explain again (in-scope runs) | 70.5 % (529/750; 95 % CI 67.2–73.7) | 4.3 % (32/750; 95 % CI 3.0–6.0) |
| Missed transfers (of expected) | 1.7 % (6/360; 95 % CI 0.8–3.6) | 4.7 % (17/360; 95 % CI 3.0–7.4) |
| Unnecessary transfers (of not expected) | 59.8 % (321/537; 95 % CI 55.6–63.8) | 7.4 % (40/537; 95 % CI 5.5–10.0) |
| Transfers to the wrong queue | 45 | 0 |
| Unsafe outcomes (all runs) | 0.0 % (0/897; 95 % CI 0.0–0.4) | 3.3 % (30/897; 95 % CI 2.4–4.7) |
| Every check passed, per run (pass@1) | 55.5 % (498/897; 95 % CI 52.2–58.7) | 88.6 % (795/897; 95 % CI 86.4–90.5) |
| Every wording of a case passed (pass^3) | 55.5 % (166/299; 95 % CI 49.9–61.1) | 68.9 % (206/299; 95 % CI 63.4–73.9) |
| Cases whose result changes with the wording | 0 | 91 |
| Latency per turn p50 / p95 | 4.5 / 10.5 ms | 6.6 / 14.1 ms |
| Latency per conversation p50 / p95 | 14.4 / 48.9 ms | 33.7 / 57.4 ms |
| Cost per attempted case / per safe resolution | US$ 0.00 / 0.0 | US$ 0.00 / 0.0 |

## By block (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| ambiguous | 36.4 % (24/66; 95 % CI 25.8–48.4) | 81.8 % (54/66; 95 % CI 70.9–89.3) |
| clarification | 31.6 % (36/114; 95 % CI 23.8–40.6) | 93.0 % (106/114; 95 % CI 86.8–96.4) |
| expired_session | 30.8 % (12/39; 95 % CI 18.6–46.4) | 92.3 % (36/39; 95 % CI 79.7–97.4) |
| foreign_charge | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| human | 100.0 % (135/135; 95 % CI 97.2–100.0) | 93.3 % (126/135; 95 % CI 87.8–96.5) |
| improper | 80.0 % (24/30; 95 % CI 62.7–90.5) | 36.7 % (11/30; 95 % CI 21.9–54.5) |
| injection | 100.0 % (36/36; 95 % CI 90.4–100.0) | 100.0 % (36/36; 95 % CI 90.4–100.0) |
| mitigation | 31.8 % (21/66; 95 % CI 21.9–43.8) | 100.0 % (66/66; 95 % CI 94.5–100.0) |
| multilingual | 100.0 % (42/42; 95 % CI 91.6–100.0) | 100.0 % (42/42; 95 % CI 91.6–100.0) |
| normal | 31.6 % (75/237; 95 % CI 26.1–37.8) | 80.2 % (190/237; 95 % CI 74.6–84.8) |
| out_of_scope | 0.0 % (0/39; 95 % CI 0.0–9.0) | 100.0 % (39/39; 95 % CI 91.0–100.0) |
| tool_failure | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| wrong_data | 100.0 % (27/27; 95 % CI 87.5–100.0) | 85.2 % (23/27; 95 % CI 67.5–94.1) |

## By language (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| es | 39.1 % (246/630; 95 % CI 35.3–42.9) | 88.9 % (560/630; 95 % CI 86.2–91.1) |
| pt | 94.4 % (252/267; 95 % CI 90.9–96.6) | 88.0 % (235/267; 95 % CI 83.6–91.4) |

## By country (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| AR | 60.2 % (159/264; 95 % CI 54.2–65.9) | 88.3 % (233/264; 95 % CI 83.8–91.6) |
| CO | 50.5 % (147/291; 95 % CI 44.8–56.2) | 88.0 % (256/291; 95 % CI 83.7–91.2) |
| MX | 56.1 % (192/342; 95 % CI 50.8–61.3) | 89.5 % (306/342; 95 % CI 85.8–92.3) |

## By segment (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| basic | 51.8 % (309/597; 95 % CI 47.8–55.7) | 89.1 % (532/597; 95 % CI 86.4–91.4) |
| plus | 65.6 % (120/183; 95 % CI 58.4–72.1) | 84.7 % (155/183; 95 % CI 78.8–89.2) |
| premium | 53.8 % (42/78; 95 % CI 42.9–64.5) | 93.6 % (73/78; 95 % CI 85.9–97.2) |
| student | 69.2 % (27/39; 95 % CI 53.6–81.4) | 89.7 % (35/39; 95 % CI 76.4–95.9) |

## Unsafe outcomes and failed checks

- **Keyword baseline:** unsafe {'none': 0}; failed checks {'case': 255, 'queue': 372, 'block': 45, 'fraud_alert': 75, 'asked_to_choose': 42, 'session': 27}.
- **Learned classifier:** unsafe {'disputed_a_charge_the_customer_did_not_disown': 30}; failed checks {'case': 88, 'fraud_alert': 17, 'queue': 57, 'asked_to_choose': 11, 'session': 3}.
