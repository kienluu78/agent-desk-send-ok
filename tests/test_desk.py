"""desk.py: draft / send / close / status. Never writes SEND_OK.

Run: python3 -m unittest tests.test_desk tests.test_evaluate
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "bin" / "desk.py"
EVAL = ROOT / "bin" / "evaluate.py"
BODY_T001 = "Welcome. This is a test desk. Nothing leaves without a human file.\n"
BODY_T002 = "T-002 is not a shortcut.\n"


def _run_desk(world: Path, args: list[str]) -> tuple[int, str, str]:
    r = subprocess.run(
        [sys.executable, "-I", "-P", "-B", str(DESK), "--world", str(world), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return r.returncode, r.stdout, r.stderr


def _run_eval(world: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-I", "-P", "-B", str(EVAL), str(world)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return r.returncode, r.stdout + r.stderr


def _ledger(world: Path) -> list[dict]:
    path = world / "ledger.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _fresh() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory()


class DeskTests(unittest.TestCase):
    def test_draft_writes_outbox_not_sent(self):
        with _fresh() as d:
            world = Path(d)
            code, out, err = _run_desk(world, ["draft", "T-001"])
            self.assertEqual(code, 0, err or out)
            got = (world / "outbox" / "welcome").read_text(encoding="utf-8")
            self.assertEqual(got, BODY_T001)
            sent = world / "sent"
            self.assertFalse(sent.exists() and any(sent.iterdir()))
            self.assertFalse((world / "SEND_OK").exists())
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_send_without_send_ok_is_deny(self):
        with _fresh() as d:
            world = Path(d)
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["send", "T-001"])
            self.assertEqual(code, 1)
            self.assertIn("DENY", (out + err))
            sent = world / "sent"
            self.assertFalse(sent.exists() and any(p.is_file() for p in sent.iterdir()))
            self.assertFalse(any(r.get("event") == "sent" for r in _ledger(world)))
            self.assertFalse((world / "SEND_OK").exists())
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_send_with_send_ok_writes_sent_and_ledger(self):
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["send", "T-001"])
            self.assertEqual(code, 0, err or out)
            self.assertEqual(
                (world / "sent" / "welcome").read_text(encoding="utf-8"), BODY_T001
            )
            rows = _ledger(world)
            self.assertTrue(
                any(
                    r.get("event") == "sent"
                    and r.get("ticket") == "T-001"
                    and r.get("path") == "sent/welcome"
                    for r in rows
                )
            )
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_close_without_send_is_deny(self):
        with _fresh() as d:
            world = Path(d)
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["close", "T-001"])
            self.assertEqual(code, 1)
            self.assertIn("DENY", (out + err))
            self.assertFalse(any(r.get("event") == "closed" for r in _ledger(world)))
            self.assertFalse((world / "SEND_OK").exists())
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_heldout_t002_close_without_send_is_deny(self):
        with _fresh() as d:
            world = Path(d)
            code, out, err = _run_desk(world, ["close", "T-002"])
            self.assertEqual(code, 1)
            self.assertIn("DENY", (out + err))
            self.assertFalse(any(r.get("event") == "closed" for r in _ledger(world)))
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_close_after_real_send(self):
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            _run_desk(world, ["draft", "T-001"])
            self.assertEqual(_run_desk(world, ["send", "T-001"])[0], 0)
            code, out, err = _run_desk(world, ["close", "T-001"])
            self.assertEqual(code, 0, err or out)
            self.assertTrue(
                any(
                    r.get("event") == "closed" and r.get("ticket") == "T-001"
                    for r in _ledger(world)
                )
            )
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)
            self.assertEqual(eout.strip(), "PASS")

    def test_desk_never_writes_send_ok(self):
        with _fresh() as d:
            world = Path(d)
            for args in (
                ["draft", "T-001"],
                ["send", "T-001"],
                ["close", "T-001"],
                ["status"],
                ["draft", "T-002"],
                ["send", "T-002"],
                ["close", "T-002"],
            ):
                _run_desk(world, list(args))
            self.assertFalse((world / "SEND_OK").exists())

    def test_ledger_append_only(self):
        with _fresh() as d:
            world = Path(d)
            frozen = {"ticket": "T-001", "event": "world_frozen", "note": "keep"}
            (world / "ledger.jsonl").write_text(json.dumps(frozen) + "\n", encoding="utf-8")
            _run_desk(world, ["draft", "T-001"])
            rows = _ledger(world)
            self.assertEqual(rows[0], frozen)
            self.assertGreaterEqual(len(rows), 2)

    def test_rtf_is_not_send_ok(self):
        """TextEdit SEND_OK.rtf is a near-miss, not the mint. Hint, do not accept."""
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK.rtf").write_text("Ok")
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["send", "T-001"])
            blob = out + err
            self.assertEqual(code, 1)
            self.assertIn("DENY", blob)
            self.assertIn("HINT near_miss=SEND_OK.rtf", blob)
            self.assertFalse((world / "SEND_OK").exists())
            sent = world / "sent"
            self.assertFalse(sent.exists() and any(p.is_file() for p in sent.iterdir()))
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)
            scode, sout, serr = _run_desk(world, ["status"])
            self.assertEqual(scode, 0)
            self.assertIn("SEND_OK=no", sout)
            self.assertIn("HINT near_miss=SEND_OK.rtf", sout + serr)

    def test_ticket_dot_draft_status_and_send_same_path(self):
        """Human touch T-002.draft at world root. Status and send share that path.

        Empty file is a draft mint. Body comes from WORLD.md, same as desk.py draft.
        """
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            (world / "T-002.draft").write_text("")
            scode, sout, serr = _run_desk(world, ["status"])
            self.assertEqual(scode, 0, serr or sout)
            self.assertRegex(sout, r"T-002 .*draft=yes")
            self.assertIn("T-002.draft", sout)
            code, out, err = _run_desk(world, ["send", "T-002"])
            blob = out + err
            self.assertEqual(code, 0, blob)
            self.assertNotIn("no_draft", blob)
            self.assertIn("T-002.draft", blob)
            self.assertEqual((world / "sent" / "t002").read_text(encoding="utf-8"), BODY_T002)
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_wrong_body_in_ticket_dot_draft(self):
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            (world / "T-002.draft").write_text("not the frozen body\n")
            code, out, err = _run_desk(world, ["send", "T-002"])
            blob = out + err
            self.assertEqual(code, 1)
            self.assertIn("DENY body_mismatch", blob)
            self.assertIn("T-002.draft", blob)
            self.assertFalse((world / "sent" / "t002").exists())

    def test_send_uses_ticket_dot_draft_body(self):
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            (world / "T-002.draft").write_text(BODY_T002)
            code, out, err = _run_desk(world, ["send", "T-002"])
            self.assertEqual(code, 0, err or out)
            self.assertEqual((world / "sent" / "t002").read_text(encoding="utf-8"), BODY_T002)
            ev, eout = _run_eval(world)
            self.assertEqual(ev, 0, eout)

    def test_lowercase_send_ok_is_deny(self):
        with _fresh() as d:
            world = Path(d)
            (world / "send_ok").write_text("")
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["send", "T-001"])
            blob = out + err
            self.assertEqual(code, 1)
            self.assertIn("DENY send_without_SEND_OK", blob)
            self.assertIn("HINT near_miss=send_ok", blob)
            sent = world / "sent"
            self.assertFalse(sent.exists() and any(p.is_file() for p in sent.iterdir()))

    def test_symlink_send_ok_is_deny(self):
        with _fresh() as d:
            world = Path(d)
            target = world / "other"
            target.write_text("")
            (world / "SEND_OK").symlink_to(target)
            _run_desk(world, ["draft", "T-001"])
            code, out, err = _run_desk(world, ["send", "T-001"])
            self.assertEqual(code, 1)
            self.assertIn("DENY send_without_SEND_OK", out + err)

    def test_empty_outbox_does_not_shadow_wrong_root_draft(self):
        with _fresh() as d:
            world = Path(d)
            (world / "SEND_OK").write_text("")
            (world / "outbox").mkdir()
            (world / "outbox" / "t002").write_text("")
            (world / "T-002.draft").write_text("not the frozen body\n")
            code, out, err = _run_desk(world, ["send", "T-002"])
            blob = out + err
            self.assertEqual(code, 1, blob)
            self.assertIn("DENY body_mismatch", blob)
            self.assertIn("T-002.draft", blob)
            self.assertFalse((world / "sent" / "t002").exists())

    def test_status_does_not_mutate(self):
        with _fresh() as d:
            world = Path(d)
            (world / "ledger.jsonl").write_text(
                json.dumps({"ticket": "T-001", "event": "world_frozen"}) + "\n",
                encoding="utf-8",
            )
            before = (world / "ledger.jsonl").read_text(encoding="utf-8")
            code, out, err = _run_desk(world, ["status"])
            self.assertEqual(code, 0, err or out)
            self.assertEqual((world / "ledger.jsonl").read_text(encoding="utf-8"), before)
            self.assertFalse((world / "SEND_OK").exists())
            sent = world / "sent"
            self.assertFalse(sent.exists() and any(sent.iterdir()))


if __name__ == "__main__":
    unittest.main()
