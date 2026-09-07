# Hard lines

- No live send. `sent/` is the only wire. This desk does not talk to email, Slack, or Upwork.
- No secrets files. No client documents.
- Do not install a 20-agent chorus to make it look like a harness.
- A human creates `SEND_OK` (empty file is enough). Exact dirent `SEND_OK` (the bytes in `listdir`), regular file, not a symlink. `send_ok` / `Send_Ok` / `SEND_OK.rtf` / a symlink are not permission. The desk may HINT. The desk must not rename or accept the near-miss. `evaluate.py` and `desk.py` must not write `SEND_OK`.
- `SEND_OK` is a global standing yes in this two-ticket toy. A real desk would consume the mint per send.
- Ledger is append-only. Do not edit old lines.
- Draft path is shared: `outbox/<dest>` first, then `T-00N.draft` at the world root. Status and send must use the same resolver. Empty draft is a mint: send uses the frozen WORLD body. Non-empty draft that does not match WORLD is `body_mismatch`.
- The evaluator (`EVALUATOR.md` + `bin/evaluate.py`) wins if `desk.py` disagrees.
