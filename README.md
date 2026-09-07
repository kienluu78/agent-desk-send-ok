# agent-desk-send-ok

**Author:** [Kien Luu](https://www.upwork.com/freelancers/~01013a38cf9348cea9)  
**License:** MIT

A tiny agent desk. The model can draft. Send is refused until a human creates an exact file named `SEND_OK`.

This is a runnable example of a human gate on a side effect. It is not a framework, not a hosted product, and not a production mail or chat path. `sent/` is a folder on disk. Nothing emails or posts.

## Three beats (under 15 minutes)

From this folder:

```bash
python3 -I -P -B bin/desk.py draft T-001
python3 -I -P -B bin/desk.py send T-001
```

Send is denied (`DENY send_without_SEND_OK`). Then:

```bash
touch SEND_OK
python3 -I -P -B bin/desk.py send T-001
python3 -I -P -B bin/desk.py close T-001
python3 -I -P -B bin/evaluate.py
```

Evaluator prints `PASS`.

Green chart (must fail): closing the held-out ticket without a send.

```bash
python3 -I -P -B bin/desk.py close T-002
python3 -I -P -B bin/evaluate.py
```

That close is denied. If a ledger `closed` line appears without a prior `sent` line, evaluate fails (`FAIL R3`).

## What SEND_OK is

- Exact directory entry `SEND_OK` (the bytes in `listdir`)
- Regular file, not a symlink
- `send_ok`, `Send_Ok`, and `SEND_OK.rtf` are not permission. The desk may HINT. It must not rename them into permission.

`desk.py` and `evaluate.py` never write `SEND_OK`.

In this two-ticket toy, `SEND_OK` is a standing yes. A real desk would consume the mint per send.

## Tests

```bash
python3 -I -P -B -m unittest discover -s tests -q
```

## Related

JSON Schema contracts (HITL proposals, provenance atoms, bounded goals):  
https://github.com/kienluu78/agent-ops-contracts

I offer **AI agent and automation rescue**: reproduce failures, fix root causes, put a human gate on the wire, and leave a short runbook so you can run the desk without me.

## Disclaimer

Illustrative of a pattern used in real agent ops. Not a compliance certification and not legal advice. Adapt the mint and ledger to your environment.

---

Copyright (c) 2026 Kien Luu
