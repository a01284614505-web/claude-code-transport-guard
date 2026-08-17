#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import settings

original = {
    "model": "existing-model",
    "hooks": {
        "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "/keep/read"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "/keep/stop"}]}],
    },
}
with tempfile.TemporaryDirectory() as tmp:
    install_dir = Path(tmp) / "ccguard"
    data = settings.install(json.loads(json.dumps(original)), install_dir)
    data = settings.install(data, install_dir)
    counts = settings.status(data)
    assert counts == {"PreToolUse": 1, "UserPromptSubmit": 1}, counts
    assert data["model"] == "existing-model"
    assert any(item.get("matcher") == "Read" for item in data["hooks"]["PreToolUse"])
    removed = settings.remove(data)
    assert removed == original, (removed, original)
print("settings lifecycle: ok")
