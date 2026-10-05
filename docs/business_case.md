# Why disputes, and what VERA is worth

The figures below are aggregates the team computed from the LATAM Bank dataset, whose complaints were recorded between June 2023 and June 2026. They are counts and rates: no record of the dataset is in this repository. What VERA changes was measured only in an offline simulation, and the yearly figures at the end are a **projection**, not a measurement.

## Why disputes

| In the dataset | Value |
|---|---:|
| Complaints | 67,095 |
| Disputes: unrecognized charges and improper charges | 24,491 (36.5 %) |
| Unrecognized charges / improper charges | 12,297 / 12,194 |
| Disputes that missed their service deadline | 20.2 % |
| Average days to resolve a dispute | 15.5 |
| Disputes resolved or closed when the data was extracted | 24.1 % |
| Disputes from customers who had complained before | 15.0 % |
| Received through the call center / through the regulator | 50.5 % / 1.1 % |

- **Disputes are a third of all complaints.** In this synthetic data, complaints spread almost evenly over five subcategories, and the two that are disputes add up to 36.5 %.
- **Every dispute starts with a question the bank's records can answer:** which charge, and what happened to it. A first contact can do that without a person, and that is what VERA does.
- **One in five missed its deadline, and only a quarter were resolved or closed.** A case registered at the first contact, with its legal deadline dated and its facts verified, gives the analyst a head start. Whether it shortens the 15.5 days, only a pilot can tell.

## What the data does not allow

- **A complaint cannot be traced to its charge.** Of the 16,257 disputes that name an affected product, none names a product of the customer who complains. None links to the call that originated it, and two thirds (66.8 %) do not state the amount claimed.
- **So the complaints cannot be the ground truth.** The evaluation is built on transactions, which pass the pipeline's contracts with no row in quarantine ([data quality report](data_quality_report.json)), and each case's label is known by construction from the policy ([evaluation](evaluation/README.md)). In the conversation, VERA asks the customer which charge instead of assuming it.

## A projection, not a measurement

Each assumption is stated:

1. **Volume:** 24,491 disputes in 1,097 days of complaints, about 8,150 a year, for a bank of 150,000 customers.
2. **Share resolved safely without a person:** 44.5 %, from the sealed held-out run of the learned classifier, the clean measurement. The rerun under policy v1.5 reached 52.0 % with the classifier and with Claude over it, but it is labeled not clean ([results at a glance](../README.md#results-at-a-glance)).
3. **Cost of the language model:** US$ 0.0038 per attempted case, as measured in that rerun. With Claude reading every first contact, about US$ 31 a year.
4. **Cost of a first contact handled by a person:** it is not in the dataset, so the table shows three values.

| Assumed cost of a first contact handled by a person | US$ 2 | US$ 5 | US$ 10 |
|---|---:|---:|---:|
| Agent cost avoided per year at 44.5 % (about 3,630 contacts) | US$ 7,300 | US$ 18,100 | US$ 36,300 |
| Agent cost avoided per year at 52.0 % (about 4,240 contacts) | US$ 8,500 | US$ 21,200 | US$ 42,400 |
| Language model cost per year | US$ 31 | US$ 31 | US$ 31 |

What the projection leaves out:

- **The analyst still decides every dispute.** VERA does the first contact, not the resolution.
- **The server, its operation and the people who keep the rules and the legal texts current.**
- **Real customers phrase things unlike the team's wordings.** The human blind set is pending.
- **Any effect on the 15.5 days or on the missed deadlines,** which only a pilot could measure.

**How to measure it:** a pilot in shadow mode, where VERA drafts and an analyst decides, comparing first-contact resolution, transfers and minutes per contact with the current process.

## How the figures were computed

DuckDB over the complaints and products of the dataset, outside this repository ([datasheet](datasheet.md)). The queries count rows and average flags; none prints a record.

- **A dispute** is a complaint whose subcategory is «Cargo no reconocido» or «Cobro indebido».
- **Missed deadline, days and repeat customers** come from `sla_breached`, the mean of `resolution_days` and `is_repeat_complainer`.
- **Resolved or closed** counts the statuses Resolved and Closed.
- **The product check** joins `affected_product_id` with the products and compares their owner with the customer who complains.
- **The period** runs from the first to the last `creation_date` of the complaints.
