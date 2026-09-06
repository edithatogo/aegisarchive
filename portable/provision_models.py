#!/usr/bin/env python3
"""Provision pinned GGUF/speech assets using only Python's standard library.

A completed file is published only after its size and SHA-256 match the lock.
Interrupted transfers remain in .part files and resume on the next invocation.
"""
from __future__ import annotations

import argparse
import datetime
import email.utils
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ValueError("Refusing download redirect outside HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def matches(path: Path, entry: dict) -> bool:
    return (path.is_file() and path.stat().st_size == entry["size_bytes"]
            and digest(path) == entry["sha256"])


def source_inventory(lock: dict) -> dict:
    """Licence and source pins only. Presence of this record is not native inference."""
    models = []
    for model in lock["models"]:
        models.append({
            "role": model["role"],
            "repo": model.get("repo"),
            "revision": model.get("revision"),
            "license": model.get("license"),
            "parameters_billions": model.get("parameters_billions"),
            "files": [{key: entry[key] for key in ("path", "url", "sha256", "size_bytes")}
                      for entry in model["files"]],
        })
    return {"schema_version": 1, "kind": "licence_source_inventory",
            "inference_claimed": False, "models": models}


def digest_nofollow(path: Path) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        result = hashlib.sha256()
        while True:
            block = os.read(fd, 8 * 1024 * 1024)
            if not block:
                break
            result.update(block)
        return result.hexdigest()
    finally:
        os.close(fd)


def locate_cache_file(root: Path, relative: str):
    """Reject dest or ancestor symlinks and paths that escape the cache root."""
    root = Path(root).resolve()
    cursor = root
    info = None
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        try:
            info = os.lstat(cursor)
        except FileNotFoundError:
            return None, "missing"
        if stat.S_ISLNK(info.st_mode):
            return None, "symlink_rejected"
    if info is None or not stat.S_ISREG(info.st_mode):
        return None, "missing"
    resolved = cursor.resolve(strict=True)
    if not resolved.is_relative_to(root):
        return None, "path_escape"
    return cursor, None


def audit_cache(lock: dict, root: Path, selected: set) -> dict:
    """Offline SHA-256 audit. Missing or mismatched files fail closed; no inference."""
    files = []
    complete = True
    root = Path(root)
    for model in lock["models"]:
        if model["role"] not in selected:
            continue
        for entry in model["files"]:
            destination, status = locate_cache_file(root, entry["path"])
            record = {key: entry[key] for key in ("path", "url", "sha256", "size_bytes")}
            if status is not None:
                record["status"] = status
                complete = False
            elif destination.stat().st_size != entry["size_bytes"]:
                record["status"] = "size_mismatch"
                complete = False
            elif digest_nofollow(destination) != entry["sha256"]:
                record["status"] = "digest_mismatch"
                complete = False
            else:
                record["status"] = "verified"
            files.append(record)
    return {"schema_version": 1, "kind": "model_cache_audit", "complete": complete,
            "inference_claimed": False, "files": files}


def write_provenance(destination: Path, payload: dict) -> Path:
    """Write a sidecar receipt next to a verified file. Never claims inference."""
    sidecar = destination.with_name(destination.name + ".provenance.json")
    body = {"schema_version": 1, "kind": "locked_asset_provenance",
            "inference_claimed": False}
    body.update(payload)
    if body.get("inference_claimed"):
        raise ValueError("Provenance must not claim inference")
    write_json(sidecar, body)
    return sidecar


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix="." + path.name + "-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(payload, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink()
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_lock(path: Path) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1 or not lock.get("models"):
        raise ValueError("Unsupported or empty model lock")
    seen, roles = set(), set()
    for model in lock["models"]:
        role = model["role"]
        if not re.fullmatch(r"[a-z]+", role) or role in roles:
            raise ValueError("Invalid or duplicate model role")
        roles.add(role)
        for entry in model["files"]:
            name = entry["path"]
            relative = PurePosixPath(name)
            if (not name or "\\" in name or ":" in name or relative.is_absolute()
                    or ".." in relative.parts or len(relative.parts) != 2
                    or relative.parts[0] != role or name != str(relative)):
                raise ValueError(f"Unsafe asset path: {name}")
            if name in seen:
                raise ValueError(f"Duplicate asset path: {name}")
            seen.add(name)
            url = urllib.parse.urlsplit(entry["url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError(f"Asset URL must use HTTPS: {name}")
            if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
                raise ValueError(f"Invalid asset SHA-256: {name}")
            if type(entry["size_bytes"]) is not int or entry["size_bytes"] <= 0:
                raise ValueError(f"Invalid asset size: {name}")
    return lock


def retry_delay(error: Exception, attempt: int) -> float:
    delay = min(2 ** attempt, 60)
    if isinstance(error, urllib.error.HTTPError):
        value = error.headers.get("Retry-After", "")
        try:
            return max(delay, float(value))
        except ValueError:
            try:
                deadline = email.utils.parsedate_to_datetime(value)
                return max(delay, deadline.timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass
    return delay


def fetch(entry: dict, destination: Path, *, offline: bool = False,
          attempts: int = 6, opener=None) -> str:
    if destination.is_symlink():
        raise ValueError(f"Refusing symlink destination: {destination}")
    if matches(destination, entry):
        return "cached"
    if offline:
        raise ValueError(f"Missing or invalid offline asset: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.is_symlink():
        raise ValueError(f"Refusing symlink partial: {partial}")
    opener = opener or urllib.request.build_opener(HTTPSRedirectHandler())
    for attempt in range(attempts):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset >= entry["size_bytes"]:
                if matches(partial, entry):
                    os.replace(partial, destination)
                    return "downloaded"
                # Keep corrupt bytes for inspection, but do not resume them.
                os.replace(partial, partial.with_name(partial.name + ".invalid"))
                offset = 0
            headers = {"User-Agent": "AegisArchive-model-provisioner/1", "Accept-Encoding": "identity"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(entry["url"], headers=headers)
            with opener.open(request, timeout=120) as response:
                status = response.status
                if status == 206:
                    expected = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                    if (not expected or int(expected[1]) != offset
                            or int(expected[2]) != entry["size_bytes"] - 1
                            or int(expected[3]) != entry["size_bytes"]):
                        raise ValueError("Server returned inconsistent Content-Range")
                elif status == 200:
                    # A server may ignore Range; restart without duplicating bytes.
                    offset = 0
                else:
                    raise ValueError(f"Unexpected download response: {status}")
                if response.headers.get("Content-Encoding", "identity") not in ("identity", ""):
                    raise ValueError("Encoded downloads cannot be safely resumed")
                with partial.open("ab" if offset else "wb") as output:
                    while True:
                        block = response.read(min(1024 * 1024, entry["size_bytes"] - offset + 1))
                        if not block:
                            break
                        if offset + len(block) > entry["size_bytes"]:
                            raise ValueError("Download exceeds locked size")
                        output.write(block)
                        offset += len(block)
                    output.flush()
                    os.fsync(output.fileno())
            if not matches(partial, entry):
                raise ValueError(f"Incomplete download or SHA-256 mismatch: {entry['path']}")
            os.replace(partial, destination)
            return "downloaded"
        except (OSError, ValueError, http.client.HTTPException) as error:
            if attempt + 1 == attempts:
                raise
            delay = retry_delay(error, attempt)
            print(f"Retry {entry['path']} in {delay:g}s: {error}", file=sys.stderr, flush=True)
            time.sleep(delay)
    raise RuntimeError("No download attempts configured")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("model-lock.json"))
    parser.add_argument("--output", type=Path, help="Model directory or inventory JSON path")
    parser.add_argument("--roles", nargs="+", help="Optional subset of model roles")
    parser.add_argument("--offline", action="store_true", help="Verify cached files without network access")
    parser.add_argument("--inventory", action="store_true",
                        help="Write licence/source inventory; does not download or infer")
    parser.add_argument("--audit", action="store_true",
                        help="Offline SHA-256 audit; exit 1 unless every selected file verifies")
    parser.add_argument("--attempts", type=int, default=6)
    args = parser.parse_args(argv)
    if args.attempts < 1:
        parser.error("--attempts must be positive")
    if args.output is None:
        parser.error("--output is required")
    lock = load_lock(args.lock)
    available = {model["role"] for model in lock["models"]}
    selected = set(args.roles or available)
    if not selected <= available:
        parser.error("Unknown role(s): " + ", ".join(sorted(selected - available)))
    if args.inventory:
        payload = source_inventory(lock)
        payload["lock_sha256"] = digest(args.lock)
        write_json(args.output.resolve(), payload)
        print(json.dumps({"inventory": str(args.output.resolve()), "models": len(payload["models"]),
                          "inference_claimed": False}))
        return 0
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.audit:
        receipt = audit_cache(lock, root, selected)
        receipt["lock_sha256"] = digest(args.lock)
        receipt["verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(root / "model-audit.json", receipt)
        print(json.dumps({"complete": receipt["complete"], "inference_claimed": False,
                          "files": len(receipt["files"])}), flush=True)
        return 0 if receipt["complete"] else 1
    receipt = {"schema_version": 1, "lock_sha256": digest(args.lock), "files": [],
               "inference_claimed": False}
    for model in lock["models"]:
        if model["role"] not in selected:
            continue
        for entry in model["files"]:
            destination = root / entry["path"]
            if not destination.resolve().is_relative_to(root):
                raise ValueError(f"Asset destination escapes output directory: {entry['path']}")
            result = fetch(entry, destination, offline=args.offline, attempts=args.attempts)
            receipt["files"].append({**entry, "status": result})
            write_provenance(destination, {
                "path": entry["path"], "url": entry["url"], "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"], "license": model.get("license"),
                "repo": model.get("repo"), "revision": model.get("revision"),
                "status": result,
            })
            print(f"{result}: {entry['path']}", flush=True)
    receipt["verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(root / "model-receipt.json", receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        print(f"Model provisioning failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
