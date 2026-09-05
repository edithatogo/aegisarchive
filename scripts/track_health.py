#!/usr/bin/env python3
"""
AegisArchive - Conductor Track Health

Parses every conductor/tracks/*/ directory (metadata.json, plan.md,
evidence.jsonl) plus conductor/backlog.md and reports:

  - in_progress tracks older than 14 days (by metadata.updated_at)
  - completed tracks that still have unticked plan boxes
  - planned tracks without spec.md
  - tracks with metadata.json but no evidence.jsonl (or an empty one)
  - backlog rows whose track_id has no track directory
  - completed tracks without an entry in conductor/lessons.md
  - legacy tracks (plan.md only, no metadata.json) as informational

Output is Markdown. Exit code is 0 unless --strict is given and at least one
finding exists. Python 3 standard library only.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, 'conductor', 'tracks')
BACKLOG = os.path.join(ROOT, 'conductor', 'backlog.md')
LESSONS = os.path.join(ROOT, 'conductor', 'lessons.md')
STALE_DAYS = 14

UNTICKED = re.compile(r'^\s*- \[ \]', re.M)
TICKED = re.compile(r'^\s*- \[x\]', re.M | re.I)
FENCE = re.compile(r'^```.*?^```[ \t]*$', re.M | re.S)


def strip_fences(text):
    """Remove fenced code blocks so quoted file contents are not counted as tasks."""
    return FENCE.sub('', text)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.read()


def parse_ts(value):
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_tracks():
    tracks = []
    if not os.path.isdir(TRACKS):
        return tracks
    for name in sorted(os.listdir(TRACKS)):
        d = os.path.join(TRACKS, name)
        if not os.path.isdir(d) or name.startswith('.'):
            continue
        t = {'id': name, 'dir': d, 'meta': None, 'plan': '', 'spec': False, 'evidence_lines': 0}
        mp = os.path.join(d, 'metadata.json')
        if os.path.isfile(mp):
            try:
                t['meta'] = json.loads(read(mp))
            except json.JSONDecodeError as exc:
                t['meta_error'] = str(exc)
        pp = os.path.join(d, 'plan.md')
        if os.path.isfile(pp):
            t['plan'] = strip_fences(read(pp))
        t['spec'] = os.path.isfile(os.path.join(d, 'spec.md'))
        ep = os.path.join(d, 'evidence.jsonl')
        if os.path.isfile(ep):
            t['evidence_lines'] = sum(1 for line in read(ep).splitlines() if line.strip())
        tracks.append(t)
    return tracks


def backlog_track_ids():
    ids = []
    if not os.path.isfile(BACKLOG):
        return ids
    for line in read(BACKLOG).splitlines():
        m = re.match(r'^\|\s*P[0-3]\s*\|\s*([^|]+?)\s*\|', line)
        if m:
            ids.append(m.group(1).strip('` '))
    return ids


def lesson_track_ids():
    if not os.path.isfile(LESSONS):
        return set()
    return set(re.findall(r'^## \d{4}-\d{2}-\d{2} — (\S+)', read(LESSONS), re.M))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report conductor track health as Markdown.")
    ap.add_argument('--strict', action='store_true', help='exit 1 when any finding exists')
    ap.add_argument('--now', default=None, help='override current time (ISO-8601 UTC, for tests)')
    args = ap.parse_args(argv)

    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    tracks = load_tracks()
    lessons = lesson_track_ids()
    findings = []
    info = []

    print("# Conductor track health\n")
    print("| track | type | status | unticked | ticked | evidence lines | spec |")
    print("| :-- | :-- | :-- | --: | --: | --: | :-- |")
    for t in tracks:
        meta = t['meta'] or {}
        status = meta.get('status', 'legacy')
        unt = len(UNTICKED.findall(t['plan']))
        tick = len(TICKED.findall(t['plan']))
        print(f"| `{t['id']}` | {meta.get('type', '-')} | {status} | {unt} | {tick} | {t['evidence_lines']} | {'yes' if t['spec'] else 'no'} |")

        if 'meta_error' in t:
            findings.append(f"`{t['id']}`: metadata.json is not valid JSON ({t['meta_error']})")
            continue
        if t['meta'] is None:
            info.append(f"`{t['id']}`: legacy track (plan.md only; no metadata.json)")
            continue
        if status == 'in_progress':
            upd = parse_ts(meta.get('updated_at'))
            if upd is None:
                findings.append(f"`{t['id']}`: in_progress without a parseable updated_at")
            elif (now - upd).days > STALE_DAYS:
                findings.append(f"`{t['id']}`: in_progress for {(now - upd).days} days (> {STALE_DAYS})")
        if status == 'completed' and unt:
            findings.append(f"`{t['id']}`: completed but {unt} plan box(es) unticked")
        if status == 'completed' and t['id'] not in lessons:
            findings.append(f"`{t['id']}`: completed without an entry in conductor/lessons.md")
        if status == 'planned' and not t['spec']:
            findings.append(f"`{t['id']}`: planned without spec.md")
        if t['evidence_lines'] == 0:
            findings.append(f"`{t['id']}`: missing or empty evidence.jsonl")

    known = {t['id'] for t in tracks}
    for tid in backlog_track_ids():
        if tid not in known and tid != 'new':
            findings.append(f"backlog row references unknown track `{tid}`")

    print("\n## Findings\n")
    if findings:
        for f in findings:
            print(f"- {f}")
    else:
        print("- none")
    if info:
        print("\n## Informational\n")
        for i in info:
            print(f"- {i}")
    print(f"\n{len(findings)} finding(s) across {len(tracks)} track(s).")
    return 1 if (findings and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
