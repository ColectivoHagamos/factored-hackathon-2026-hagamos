# Evaluation · dev set

Offline simulation: a scripted customer talks to the application in process; not production. Cases: 98, each run three times with three different wordings; 36 % in Portuguese. SHA-256 of the cases: `e7ea18b039bc441c771f9304c18fa86ecf4ddee1977f6be32fe4987a2b83445a`.

## Official metrics

| Metric | Keyword baseline | Learned classifier |
|---|---|---|
| Safe automated resolution (all in-scope runs) | 34.5 % (87/252; 95 % CI 28.9–40.6) | 34.5 % (87/252; 95 % CI 28.9–40.6) |
| Attempted automation (in-scope runs) | 100.0 % (252/252; 95 % CI 98.5–100.0) | 100.0 % (252/252; 95 % CI 98.5–100.0) |
| Containment (no transfer) | 43.9 % (129/294; 95 % CI 38.3–49.6) | 43.9 % (129/294; 95 % CI 38.3–49.6) |
| Customer had to explain again (in-scope runs) | 20.6 % (52/252; 95 % CI 16.1–26.1) | 2.8 % (7/252; 95 % CI 1.4–5.6) |
| Missed transfers (of expected) | 0.0 % (0/165; 95 % CI 0.0–2.3) | 0.0 % (0/165; 95 % CI 0.0–2.3) |
| Unnecessary transfers (of not expected) | 0.0 % (0/129; 95 % CI 0.0–2.9) | 0.0 % (0/129; 95 % CI 0.0–2.9) |
| Transfers to the wrong queue | 0 | 0 |
| Unsafe outcomes (all runs) | 0.0 % (0/294; 95 % CI 0.0–1.3) | 0.0 % (0/294; 95 % CI 0.0–1.3) |
| Deadlines equal to the truth table (runs with a case) | 100.0 % (117/117; 95 % CI 96.8–100.0) | 100.0 % (117/117; 95 % CI 96.8–100.0) |
| Replies blocked by the output validator (runs) | 0.0 % (0/294; 95 % CI 0.0–1.3) | 0.0 % (0/294; 95 % CI 0.0–1.3) |
| Every check passed, per run (pass@1) | 100.0 % (294/294; 95 % CI 98.7–100.0) | 100.0 % (294/294; 95 % CI 98.7–100.0) |
| Every wording of a case passed (pass^3) | 100.0 % (98/98; 95 % CI 96.2–100.0) | 100.0 % (98/98; 95 % CI 96.2–100.0) |
| Cases whose result changes with the wording | 0 | 0 |
| Latency per turn p50 / p95 | 5.2 / 11.1 ms | 6.2 / 12.7 ms |
| Latency per conversation p50 / p95 | 26.5 / 52.5 ms | 28.9 / 58.1 ms |
| Cost per attempted case / per safe resolution | US$ 0.00 / 0.0 | US$ 0.00 / 0.0 |

## By block (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| ambiguous | 100.0 % (15/15; 95 % CI 79.6–100.0) | 100.0 % (15/15; 95 % CI 79.6–100.0) |
| clarification | 100.0 % (30/30; 95 % CI 88.6–100.0) | 100.0 % (30/30; 95 % CI 88.6–100.0) |
| expired_session | 100.0 % (6/6; 95 % CI 61.0–100.0) | 100.0 % (6/6; 95 % CI 61.0–100.0) |
| foreign_charge | 100.0 % (12/12; 95 % CI 75.8–100.0) | 100.0 % (12/12; 95 % CI 75.8–100.0) |
| human | 100.0 % (75/75; 95 % CI 95.1–100.0) | 100.0 % (75/75; 95 % CI 95.1–100.0) |
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
| es | 100.0 % (189/189; 95 % CI 98.0–100.0) | 100.0 % (189/189; 95 % CI 98.0–100.0) |
| pt | 100.0 % (105/105; 95 % CI 96.5–100.0) | 100.0 % (105/105; 95 % CI 96.5–100.0) |

## By country (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| AR | 100.0 % (69/69; 95 % CI 94.7–100.0) | 100.0 % (69/69; 95 % CI 94.7–100.0) |
| CO | 100.0 % (84/84; 95 % CI 95.6–100.0) | 100.0 % (84/84; 95 % CI 95.6–100.0) |
| MX | 100.0 % (141/141; 95 % CI 97.4–100.0) | 100.0 % (141/141; 95 % CI 97.4–100.0) |

## By segment (pass@1)

| | Keyword baseline | Learned classifier |
|---|---|---|
| basic | 100.0 % (192/192; 95 % CI 98.0–100.0) | 100.0 % (192/192; 95 % CI 98.0–100.0) |
| plus | 100.0 % (51/51; 95 % CI 93.0–100.0) | 100.0 % (51/51; 95 % CI 93.0–100.0) |
| premium | 100.0 % (36/36; 95 % CI 90.4–100.0) | 100.0 % (36/36; 95 % CI 90.4–100.0) |
| student | 100.0 % (15/15; 95 % CI 79.6–100.0) | 100.0 % (15/15; 95 % CI 79.6–100.0) |

## Unsafe outcomes and failed checks

- **Keyword baseline:** unsafe {'none': 0}; failed checks {'none': 0}.
- **Learned classifier:** unsafe {'none': 0}; failed checks {'none': 0}.
