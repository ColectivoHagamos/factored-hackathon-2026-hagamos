# Data freshness and updates

The dataset is static: its last event is on 2026-06-18, and that date is the simulated clock of the policy (`system_clock`). The pipeline is built as if new batches kept arriving, and a generated update fixture proves it (`tests/pipeline/test_update_fixture.py`).

## Cut

- The **data cut** is the latest event in gold (`max(occurred_at)` of `charges`), recorded in the gold manifest as `data_cut`.
- The **simulated clock** of the policy decides "today" for every deadline. In production it is the real date; in the demo it stays at 2026-06-18, so the legal clock gives the same dates on every run.

## When a batch arrives

| Layer | Behavior |
|---|---|
| Bronze | New or changed files produce a new manifest (size and SHA-256 per file); unchanged sources rewrite nothing |
| Silver | Every row is checked again against its contract. When a key repeats, the version with the latest process date wins, and the earlier one stays in quarantine as `duplicate_key`. A status change (pending to approved or reversed) is a new version of the same transaction |
| Gold | Rebuilt aside and swapped only on success, so a failed build keeps the previous gold. Each row records its source file and the bronze manifest |
| Demo subset | Rebuilt with the same key, so pseudonyms stay stable; the leak test runs again before deploying |

## Late events

Each daily file also contains events from the early hours of the next day: 1,106,307 transactions (25 %) occur on the day after their process date. Silver keeps the event time (`occurred_at`) for every deadline and uses the process date only to choose between versions of a key.

## What the fixture proves

The generated batch has a new charge, a status change and two invalid rows. After loading it:
- gold gains exactly the new charge, and only the changed charge differs;
- the invalid rows are quarantined with their reasons;
- the superseded version is kept in quarantine;
- the cut and the manifest move;
- reloading the same batch changes nothing.
