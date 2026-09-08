"""Crash safe checkpoint and segment storage for resumable mirrors.

The checkpoint is a small JSON document whose references are only published
after the corresponding segment has been atomically replaced into place.
Secrets are deliberately not accepted in the serialised state.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class CheckpointError(ValueError):
    """The checkpoint or one of its referenced segments cannot be trusted."""


class MirrorCheckpoint:
    VERSION = 1

    def __init__(self, root: str | os.PathLike[str], profile_id: str, profile_hash: str):
        self.root = Path(root)
        self.segments = self.root / "segments"
        self.path = self.root / "checkpoint.json"
        self.profile_id, self.profile_hash = profile_id, profile_hash
        self.root.mkdir(parents=True, exist_ok=True)
        self.segments.mkdir(exist_ok=True)

    def _atomic_bytes(self, path: Path, data: bytes) -> None:
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def append_segment(self, sequence: int, data: bytes) -> dict[str, Any]:
        if sequence < 0 or not isinstance(data, bytes):
            raise ValueError("invalid segment")
        digest = hashlib.sha256(data).hexdigest()
        name = f"segment-{sequence:08d}.bin"
        self._atomic_bytes(self.segments / name, data)
        return {"sequence": sequence, "name": name, "bytes": len(data), "sha256": digest}

    def save(self, queue: list[dict[str, Any]], visited: list[str], segments: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        state = {"version": self.VERSION, "profile_id": self.profile_id, "profile_sha256": self.profile_hash,
                 "queue": queue, "visited": visited, "segments": segments, "extra": extra}
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        self._atomic_bytes(self.path, encoded)
        return state

    def load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CheckpointError("invalid checkpoint") from exc
        if state.get("version") != self.VERSION or state.get("profile_id") != self.profile_id or state.get("profile_sha256") != self.profile_hash:
            raise CheckpointError("checkpoint does not match profile")
        for item in state.get("segments", []):
            path = self.segments / str(item.get("name", ""))
            if path.parent != self.segments or not path.is_file():
                raise CheckpointError("checkpoint references missing segment")
            data = path.read_bytes()
            if len(data) != item.get("bytes") or hashlib.sha256(data).hexdigest() != item.get("sha256"):
                raise CheckpointError("checkpoint references corrupt segment")
        return state
