"""Gate TruffleHog JSON lines without printing credential material."""

import hashlib
import json
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / ".trufflehog-fixtures.json"
FIELDS = ("detector", "commit", "file", "line", "sha256")


def fingerprint(record):
    if not isinstance(record, dict) or record.keys() != set(FIELDS):
        raise ValueError
    key = tuple(record[field] for field in FIELDS)
    detector, commit, path, line, digest = key
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/+-]{0,95}", detector)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not isinstance(path, str)
        or not path
        or type(line) is not int
        or line <= 0
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise ValueError
    return key


def load_reviewed():
    with FIXTURES.open(encoding="utf-8") as fixtures:
        records = json.load(fixtures)
    if not isinstance(records, list):
        raise ValueError
    reviewed = set()
    for record in records:
        key = fingerprint(record)
        if key[0] != "URI" or not key[2].startswith("tests/") or key in reviewed:
            raise ValueError
        reviewed.add(key)
    return reviewed


def main():
    try:
        reviewed = load_reviewed()
    except (OSError, TypeError, ValueError):
        print("Invalid TruffleHog fixture list.", file=sys.stderr)
        return 2

    allowed = 0
    unexpected = 0
    for number, line in enumerate(sys.stdin, 1):
        try:
            result = json.loads(line)
            source = result["SourceMetadata"]["Data"]["Git"]
            raw = result["Raw"]
            raw_v2 = result.get("RawV2", "")
            verified = result["Verified"]
            if not isinstance(raw, str) or not raw or not isinstance(raw_v2, str):
                raise ValueError
            if type(verified) is not bool:
                raise ValueError
            location = {
                "detector": result["DetectorName"],
                "commit": source["commit"],
                "file": source["file"],
                "line": source["line"],
            }
            values = json.dumps([raw, raw_v2], ensure_ascii=True, separators=(",", ":"))
            key = fingerprint({**location, "sha256": hashlib.sha256(values.encode()).hexdigest()})
        except (KeyError, TypeError, ValueError):
            print(f"Invalid TruffleHog result at JSON line {number}.", file=sys.stderr)
            return 2

        if not verified and key in reviewed:
            allowed += 1
        else:
            unexpected += 1
            path = location.pop("file")
            location["file_sha256"] = hashlib.sha256(path.encode()).hexdigest()
            print(json.dumps(location), file=sys.stderr)

    print(f"TruffleHog found {unexpected} new matches and {allowed} reviewed historical fixtures.")
    return int(unexpected != 0)


if __name__ == "__main__":
    sys.exit(main())
