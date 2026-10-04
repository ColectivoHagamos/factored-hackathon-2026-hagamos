# Evaluation · dev set

Offline simulation: a scripted customer talks to the application in process; not production. Cases: 88, each run three times with three different wordings; 35 % in Portuguese. SHA-256 of the cases: `1167adf640b924db6561c5e029939b4e485b98b927a5e92760a7642c42807a6a`.

## Official metrics

| Metric | Keyword baseline | Learned classifier |
|---|---|---|
| Safe automated resolution (all in-scope runs) | 39.2 % (87/222; 95 % CI 33.0–45.7) | 39.2 % (87/222; 95 % CI 33.0–45.7) |
| Attempted automation (in-scope runs) | 85.1 % (189/222; 95 % CI 79.9–89.2) | 87.8 % (195/222; 95 % CI 82.9–91.5) |
| Containment (no transfer) | 48.9 % (129/264; 95 % CI 42.9–54.9) | 48.9 % (129/264; 95 % CI 42.9–54.9) |
| Customer had to explain again (in-scope runs) | 23.4 % (52/222; 95 % CI 18.3–29.4) | 3.1 % (7/222; 95 % CI 1.5–6.4) |
| Missed transfers (of expected) | 0.0 % (0/135; 95 % CI 0.0–2.8) | 0.0 % (0/135; 95 % CI 0.0–2.8) |
| Unnecessary transfers (of not expected) | 0.0 % (0/129; 95 % CI 0.0–2.9) | 0.0 % (0/129; 95 % CI 0.0–2.9) |
| Transfers to the wrong queue | 0 | 0 |
| Unsafe outcomes (all runs) | 0.0 % (0/264; 95 % CI 0.0–1.4) | 0.0 % (0/264; 95 % CI 0.0–1.4) |
| Every check passed, per run (pass@1) | 100.0 % (264/264; 95 % CI 98.6–100.0) | 100.0 % (264/264; 95 % CI 98.6–100.0) |
| Every wording of a case passed (pass^3) | 100.0 % (88/88; 95 % CI 95.8–100.0) | 100.0 % (88/88; 95 % CI 95.8–100.0) |
| Cases whose result changes with the wording | 0 | 0 |
| Latency per turn p50 / p95 | 4.8 / 11.2 ms | 5.8 / 11.2 ms |
| Latency per conversation p50 / p95 | 30.0 / 48.3 ms | 31.3 / 45.5 ms |
| Cost per attempted case / per safe resolution | US$ 0.00 / 0.0 | US$ 0.00 / 0.0 |

## By block (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| ambiguous | 100.0 % (15/15; 95 % CI 79.6–100.0) | 100.0 % (15/15; 95 % CI 79.6–100.0) |
| clarification | 100.0 % (30/30; 95 % CI 88.6–100.0) | 100.0 % (30/30; 95 % CI 88.6–100.0) |
| expired_session | 100.0 % (6/6; 95 % CI 61.0–100.0) | 100.0 % (6/6; 95 % CI 61.0–100.0) |
| foreign_charge | 100.0 % (12/12; 95 % CI 75.8–100.0) | 100.0 % (12/12; 95 % CI 75.8–100.0) |
| human | 100.0 % (45/45; 95 % CI 92.1–100.0) | 100.0 % (45/45; 95 % CI 92.1–100.0) |
| improper | 100.0 % (6/6; 95 % CI 61.0–100.0) | 100.0 % (6/6; 95 % CI 61.0–100.0) |
| injection | 100.0 % (9/9; 95 % CI 70.1–100.0) | 100.0 % (9/9; 95 % CI 70.1–100.0) |
| mitigation | 100.0 % (30/30; 95 % CI 88.6–100.0) | 100.0 % (30/30; 95 % CI 88.6–100.0) |
| multilingual | 100.0 % (3/3; 95 % CI 43.9–100.0) | 100.0 % (3/3; 95 % CI 43.9–100.0) |
| normal | 100.0 % (63/63; 95 % CI 94.2–100.0) | 100.0 % (63/63; 95 % CI 94.2–100.0) |
| out_of_scope | 100.0 % (15/15; 95 % CI 79.6–100.0) | 100.0 % (15/15; 95 % CI 79.6–100.0) |
| tool_failure | 100.0 % (12/12; 95 % CI 75.8–100.0) | 100.0 % (12/12; 95 % CI 75.8–100.0) |
| wrong_data | 100.0 % (18/18; 95 % CI 82.4–100.0) | 100.0 % (18/18; 95 % CI 82.4–100.0) |

## By language (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| es | 100.0 % (171/171; 95 % CI 97.8–100.0) | 100.0 % (171/171; 95 % CI 97.8–100.0) |
| pt | 100.0 % (93/93; 95 % CI 96.0–100.0) | 100.0 % (93/93; 95 % CI 96.0–100.0) |

## By country (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| AR | 100.0 % (57/57; 95 % CI 93.7–100.0) | 100.0 % (57/57; 95 % CI 93.7–100.0) |
| CO | 100.0 % (75/75; 95 % CI 95.1–100.0) | 100.0 % (75/75; 95 % CI 95.1–100.0) |
| MX | 100.0 % (132/132; 95 % CI 97.2–100.0) | 100.0 % (132/132; 95 % CI 97.2–100.0) |

## By segment (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| basic | 100.0 % (177/177; 95 % CI 97.9–100.0) | 100.0 % (177/177; 95 % CI 97.9–100.0) |
| plus | 100.0 % (42/42; 95 % CI 91.6–100.0) | 100.0 % (42/42; 95 % CI 91.6–100.0) |
| premium | 100.0 % (33/33; 95 % CI 89.6–100.0) | 100.0 % (33/33; 95 % CI 89.6–100.0) |
| student | 100.0 % (12/12; 95 % CI 75.8–100.0) | 100.0 % (12/12; 95 % CI 75.8–100.0) |

## Unsafe outcomes and failed checks

- **Keyword baseline:** unsafe {'none': 0}; failed checks {'none': 0}.
- **Learned classifier:** unsafe {'none': 0}; failed checks {'none': 0}.
