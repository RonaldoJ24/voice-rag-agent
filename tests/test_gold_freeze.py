"""The gold set is frozen at tag eval-freeze-v1: any edit must be a new, deliberate freeze."""

import hashlib
import json

from voice_rag_agent.config import ROOT


def test_gold_set_matches_its_freeze_record():
    freeze = json.loads((ROOT / "eval/gold.freeze.json").read_text())
    data = (ROOT / freeze["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == freeze["sha256"]
    assert len([x for x in data.splitlines() if x.strip()]) == freeze["rows"]
