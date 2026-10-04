# Publication audit

This repository becomes public only when this audit finds nothing (plan step P57). The audit reads the current tree and the whole git history, and it never prints a sensitive value: only counts, kinds and paths.

## Last run

2026-10-04, on `development` at `4973deb`.

| Check | Scope | Result |
|---|---|---|
| Forbidden paths: dataset files, databases, serialized models, keys and environment files | Tree and history (534 blobs) | None |
| Files over 10 MB | History | None |
| Secrets and cloud data by pattern: cloud keys, private keys, language model provider keys | Tree and history | None |
| Exact values of the dataset's data dictionary | Tree and history | None |
| Real dataset identifiers: 1,210 tokens of the repository against 26,318,033 dataset values | Tree | None. The positive control found 25 of 25 columns, so the check can see a leak |
| Configuration files of development tools, signatures and session links | Tree, history and commit messages | None |
| The brand of a real bank (the product is LATAM Bank) | Tree, history and commit messages | None |
| Emojis in code or documentation | Tree | None |
| Binary documents (PDF, Word, PowerPoint) | Tree | None |

**Result: no findings and no warnings.**

The check that runs in CI on every pull request (`scripts/check_publication.py`) looks for the same patterns in the files of each change. This audit adds the whole history and the cross-check against the dataset. That cross-check needs the dataset, so it runs only on the team's machine, never in CI.

## Before the repository goes public

1. Run the audit again on the final `production` commit and update the table above.
2. Make `production` the default branch.
3. Make the repository public and check its name: `factored-hackathon-2026-hagamos`.
4. Check that the demo URL in the README answers, and that the language model key lives only in the server's environment.
