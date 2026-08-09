from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path


def _log_dir() -> Path:
    """Returns the logs/ directory next to the running application.

    In a PyInstaller-frozen build, __file__ resolves inside the onefile
    extraction tempdir, which is wiped on exit, so logs must instead live
    next to the executable itself.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "logs"
    return Path(__file__).parent.parent.parent / "logs"


class ActivityLog:
    """
    Records a structured, append-only log of every user action taken in the editor.

    Format: JSON Lines — one JSON object per line, flushed immediately after each write.
    One log file is created per session, named by start timestamp and session ID.

    Each entry always contains:
        timestamp   ISO-8601 with milliseconds
        session     8-hex-char session ID
        event       event type string

    Replay / debugging workflow:
        Each action entry includes the location (scene) ID, byte address, opcode, and
        args at the time of the operation, plus a human-readable context breadcrumb
        (e.g. "Object 0C > Startup / Idle") so failures can be reproduced step-by-step.
    """

    def __init__(self, log_dir: Path | None = None, enabled: bool = False):
        self._enabled = enabled
        self._session_id = uuid.uuid4().hex[:8]
        self._file = None
        if not self._enabled:
            return
        base = log_dir if log_dir is not None else _log_dir()
        base.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = base / f"session_{stamp}_{self._session_id}.log"
        self._file = open(log_path, "a", encoding="utf-8")
        self._write({"event": "session_start"})

    def _write(self, data: dict) -> None:
        if not self._enabled:
            return
        data["timestamp"] = datetime.now().isoformat(timespec="milliseconds")
        data["session"] = self._session_id
        self._file.write(json.dumps(data) + "\n")
        self._file.flush()

    @staticmethod
    def _cmd_dict(command) -> dict:
        if command is None:
            return {}
        return {"opcode": f"0x{command.command:02X}", "args": list(command.args)}

    def log_file_open(self, path: str) -> None:
        self._write({"event": "file_open", "path": path})

    def log_file_save(self, path: str) -> None:
        self._write({"event": "file_save", "path": path})


    def log_location_change(self, location_id: int) -> None:
        self._write({"event": "location_change", "location": location_id})

    def log_command_insert(self, location_id: int, address: int,
                           command, context: str) -> None:
        self._write({
            "event": "command_insert",
            "location": location_id,
            "address": f"0x{address:X}",
            "context": context,
            **self._cmd_dict(command),
        })

    def log_command_delete(self, location_id: int, address: int,
                           command, context: str) -> None:
        self._write({
            "event": "command_delete",
            "location": location_id,
            "address": f"0x{address:X}",
            "context": context,
            **self._cmd_dict(command),
        })

    def log_command_update(self, location_id: int, address: int,
                           old_command, new_command, context: str) -> None:
        self._write({
            "event": "command_update",
            "location": location_id,
            "address": f"0x{address:X}",
            "context": context,
            "old": self._cmd_dict(old_command),
            "new": self._cmd_dict(new_command),
        })

    def log_command_move(self, location_id: int,
                         from_address: int, to_address: int,
                         command, context: str) -> None:
        self._write({
            "event": "command_move",
            "location": location_id,
            "from_address": f"0x{from_address:X}",
            "to_address": f"0x{to_address:X}",
            "context": context,
            **self._cmd_dict(command),
        })

    def log_copy(self, location_id: int, items: list[dict]) -> None:
        self._write({
            "event": "command_copy",
            "location": location_id,
            "items": items,
        })

    def log_paste(self, location_id: int, target_address: int,
                  target_context: str, items: list[dict]) -> None:
        self._write({
            "event": "command_paste",
            "location": location_id,
            "target_address": f"0x{target_address:X}",
            "target_context": target_context,
            "items": items,
        })

    def log_tree_discrepancy(self, location_id: int,
                             discrepancies: list[str], trigger: str = "") -> None:
        self._write({
            "event": "tree_discrepancy",
            "location": location_id,
            "trigger": trigger,
            "discrepancies": discrepancies,
        })

    def close(self) -> None:
        if self._file:
            self._write({"event": "session_end"})
            self._file.close()
            self._file = None  # type: ignore[assignment]
