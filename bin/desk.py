#!/usr/bin/env python3
"""Thin desk CLI. Drafts, sends only with exact SEND_OK, refuses a green-chart close.

Does not write SEND_OK. Does not talk to email, Slack, or Upwork.
sent/ is the only wire. See ../HARD_LINES.md and ../WORLD.md.
Invoke: python3 -I -P -B bin/desk.py [--world DIR] draft|send|close|status [TICKET]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))
from evaluate import (  # frozen strings + mint gate; evaluator still wins
    BODY,
    DEST,
    exact_send_ok,
    lookalike_send_ok,
)

DEFAULT_WORLD = BIN.parent


def _reexec_isolated() -> None:
    isolated = bool(getattr(sys.flags, "isolated", 0))
    safe = bool(getattr(sys.flags, "safe_path", 0))
    if isolated and safe:
        return
    os.execv(sys.executable, [sys.executable, "-I", "-P", "-B", *sys.argv])


def _norm_body(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def _ticket(name: str | None) -> str | None:
    if not name or name not in DEST:
        return None
    return name


def _inside(world: Path, p: Path) -> bool:
    try:
        wr = world.resolve()
        pr = p.resolve()
    except OSError:
        return False
    return pr == wr or wr in pr.parents


def _send_ok(world: Path) -> bool:
    ok, _why = exact_send_ok(world)
    return ok


def _draft_candidates(world: Path, ticket: str) -> list[Path]:
    dest = DEST[ticket]
    return [
        world / "outbox" / dest,
        world / f"{ticket}.draft",
    ]


def _draft_path(world: Path, ticket: str) -> Path | None:
    """Same path for status and send. Non-empty wins over empty outbox shadow."""
    nonempty: list[Path] = []
    empty: list[Path] = []
    for p in _draft_candidates(world, ticket):
        if p.is_symlink() or not p.is_file():
            continue
        if not _inside(world, p):
            continue
        if p.stat().st_size > 0:
            nonempty.append(p)
        else:
            empty.append(p)
    if nonempty:
        return nonempty[0]
    if empty:
        return empty[0]
    return None


def _hint_near_miss(world: Path) -> None:
    hits = lookalike_send_ok(world)
    if hits:
        print("HINT near_miss=" + ",".join(hits) + " exact=SEND_OK")


def _append_ledger(world: Path, obj: dict) -> None:
    path = world / "ledger.jsonl"
    if path.is_symlink() or not _inside(world, path.parent):
        raise OSError("ledger outside world")
    line = json.dumps(obj, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    last = path.read_text(encoding="utf-8").splitlines()[-1]
    if last != line.rstrip("\n"):
        raise OSError("ledger append verify failed")


def _load_ledger(world: Path) -> list[dict]:
    path = world / "ledger.jsonl"
    if path.is_symlink() or not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            rows.append(o)
    return rows


def _has_sent_event(world: Path, ticket: str) -> bool:
    dest = DEST[ticket]
    rel = f"sent/{dest}"
    return any(
        r.get("event") == "sent" and r.get("ticket") == ticket and r.get("path") == rel
        for r in _load_ledger(world)
    )


def _deny(reason: str, ticket: str = "") -> int:
    extra = f" ticket={ticket}" if ticket else ""
    print(f"DENY {reason}{extra}")
    return 1


def _ok(msg: str) -> int:
    print(f"OK {msg}")
    return 0


def cmd_draft(world: Path, ticket: str) -> int:
    dest = DEST[ticket]
    body = BODY[ticket] + "\n"
    outbox = world / "outbox"
    if outbox.is_symlink() or (outbox.exists() and not _inside(world, outbox)):
        return _deny("outbox_escape", ticket)
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / dest
    if path.is_symlink() or not _inside(world, path):
        return _deny("outbox_escape", ticket)
    path.write_text(body, encoding="utf-8")
    _append_ledger(world, {"ticket": ticket, "event": "draft", "path": f"outbox/{dest}"})
    return _ok(f"draft path=outbox/{dest}")


def cmd_send(world: Path, ticket: str) -> int:
    dest = DEST[ticket]
    if not _send_ok(world):
        code = _deny("send_without_SEND_OK", ticket)
        _hint_near_miss(world)
        return code
    src = _draft_path(world, ticket)
    if src is None:
        return _deny("no_draft", ticket)
    expected = BODY[ticket]
    got = _norm_body(src.read_text(encoding="utf-8"))
    rel_src = src.name if src.parent == world else str(src.relative_to(world))
    if got and got != expected:
        print(f"DENY body_mismatch ticket={ticket} path={rel_src}")
        return 1
    sent_dir = world / "sent"
    if sent_dir.is_symlink() or (sent_dir.exists() and not _inside(world, sent_dir)):
        return _deny("sent_escape", ticket)
    sent_dir.mkdir(parents=True, exist_ok=True)
    rel = f"sent/{dest}"
    dest_path = sent_dir / dest
    if dest_path.is_symlink() or not _inside(world, dest_path):
        return _deny("sent_escape", ticket)
    payload = expected + "\n"
    tmp = sent_dir / (dest + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    _append_ledger(world, {"ticket": ticket, "event": "sent", "path": rel})
    os.replace(tmp, dest_path)
    return _ok(f"sent path={rel} draft={rel_src}")


def cmd_close(world: Path, ticket: str) -> int:
    dest = DEST[ticket]
    sent_path = world / "sent" / dest
    if sent_path.is_symlink() or not _inside(world, sent_path):
        return _deny("close_without_send", ticket)
    if not (_send_ok(world) and sent_path.is_file() and _has_sent_event(world, ticket)):
        return _deny("close_without_send", ticket)
    _append_ledger(world, {"ticket": ticket, "event": "closed"})
    return _ok(f"closed ticket={ticket}")


def cmd_status(world: Path, ticket: str | None) -> int:
    tickets = [ticket] if ticket else list(DEST)
    print(f"world={world}")
    print(f"SEND_OK={'yes' if _send_ok(world) else 'no'}")
    if not _send_ok(world):
        _hint_near_miss(world)
    else:
        hits = lookalike_send_ok(world)
        if hits:
            print("HINT near_miss=" + ",".join(hits) + " exact=SEND_OK")
    for t in tickets:
        dest = DEST[t]
        dpath = _draft_path(world, t)
        sent_p = world / "sent" / dest
        sent = sent_p.is_file() and not sent_p.is_symlink()
        closed = any(
            r.get("event") == "closed" and r.get("ticket") == t
            for r in _load_ledger(world)
        )
        extra = ""
        if dpath is not None:
            rel = dpath.name if dpath.parent == world else str(dpath.relative_to(world))
            extra = f" draft_path={rel}"
        print(
            f"{t} dest={dest} draft={'yes' if dpath is not None else 'no'} "
            f"sent={'yes' if sent else 'no'} closed={'yes' if closed else 'no'}{extra}"
        )
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Thin desk. Does not write SEND_OK.")
    p.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    p.add_argument("cmd", choices=["draft", "send", "close", "status"])
    p.add_argument("ticket", nargs="?", default=None)
    args = p.parse_args(argv)
    world = args.world.expanduser().resolve()
    if not world.is_dir():
        print(f"DENY not_a_dir path={world}", file=sys.stderr)
        return 1
    if args.cmd == "status":
        if args.ticket is not None and _ticket(args.ticket) is None:
            return _deny("unknown_ticket", args.ticket)
        return cmd_status(world, _ticket(args.ticket) if args.ticket else None)
    ticket = _ticket(args.ticket)
    if ticket is None:
        return _deny("unknown_ticket", args.ticket or "")
    if args.cmd == "draft":
        return cmd_draft(world, ticket)
    if args.cmd == "send":
        return cmd_send(world, ticket)
    if args.cmd == "close":
        return cmd_close(world, ticket)
    return 1


if __name__ == "__main__":
    _reexec_isolated()
    raise SystemExit(main(sys.argv[1:]))
