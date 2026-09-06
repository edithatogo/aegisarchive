"""Fail closed unless a native qualification receipt actually passed.

Never writes status passed. A missing or unreadable receipt becomes blocked.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def evaluate(path: Path) -> tuple[dict, int]:
    if not path.is_file():
        report = {
            'schema_version': 1,
            'kind': 'native_qualification',
            'status': 'blocked',
            'inference_claimed': False,
            'error': 'native-qualification.json was not written; assets may be missing or provision failed',
            'checks': {},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        return report, 1
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        report = {
            'schema_version': 1,
            'kind': 'native_qualification',
            'status': 'blocked',
            'inference_claimed': False,
            'error': 'unreadable native qualification receipt: ' + str(error),
            'checks': {},
        }
        return report, 1
    if not isinstance(report, dict):
        return {'status': 'blocked', 'inference_claimed': False,
                'error': 'receipt is not a JSON object'}, 1
    if report.get('status') == 'passed':
        return report, 0
    report.setdefault('inference_claimed', False)
    return report, 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args(argv)
    report, code = evaluate(args.receipt)
    checks = report.get('checks') if isinstance(report, dict) else {}
    summary = {name: (item.get('status') if isinstance(item, dict) else item)
               for name, item in (checks or {}).items()}
    print(json.dumps({
        'status': report.get('status'),
        'inference_claimed': report.get('inference_claimed', False),
        'checks': summary,
        'error': report.get('error'),
    }))
    if code != 0:
        print('native qualification did not pass; refusing fabricated receipts',
              file=sys.stderr)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
