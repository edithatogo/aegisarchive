#!/usr/bin/env python3
"""Fail when a SARIF file contains any medium-or-higher finding.

Standard library only. A result is medium-or-higher when either:
  * its rule has ``properties.security-severity`` >= 4.0 (CVSS scale), or
  * its effective level is ``error`` (result ``level`` or the rule's
    ``defaultConfiguration.level``).

Usage: python3 scripts/sarif_gate.py FILE.sarif [FILE2.sarif ...] [--threshold 4.0]
Exit status: 0 = no gated findings, 1 = gated findings present, 2 = usage/parse error.
"""
import argparse
import json
import sys


def _rule_index(run):
    rules = {}
    driver = run.get("tool", {}).get("driver", {})
    for rule in driver.get("rules", []) or []:
        if "id" in rule:
            rules[rule["id"]] = rule
    for ext in run.get("tool", {}).get("extensions", []) or []:
        for rule in ext.get("rules", []) or []:
            if "id" in rule:
                rules.setdefault(rule["id"], rule)
    return rules


def _severity(rule):
    props = rule.get("properties", {}) or {}
    raw = props.get("security-severity")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _location(result):
    for loc in result.get("locations", []) or []:
        phys = loc.get("physicalLocation", {})
        uri = phys.get("artifactLocation", {}).get("uri", "?")
        line = phys.get("region", {}).get("startLine", "?")
        return "%s:%s" % (uri, line)
    return "?"


def gate(paths, threshold):
    failures = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            sarif = json.load(fh)
        if not isinstance(sarif, dict) or not isinstance(sarif.get("runs"), list) or not sarif["runs"]:
            raise ValueError("SARIF must contain at least one run")
        for run in sarif["runs"]:
            if not isinstance(run, dict) or not isinstance(run.get("results", []), list):
                raise ValueError("Invalid SARIF run/results")
            if any(inv.get("executionSuccessful") is False for inv in run.get("invocations", [])):
                raise ValueError("SARIF scanner execution failed")
            rules = _rule_index(run)
            for result in run.get("results", []) or []:
                rule = rules.get(result.get("ruleId"), {})
                if not rule and "ruleIndex" in result:
                    index = result["ruleIndex"]
                    definitions = run.get("tool", {}).get("driver", {}).get("rules", [])
                    if not isinstance(index, int) or index < 0 or index >= len(definitions):
                        raise ValueError("Invalid SARIF ruleIndex")
                    rule = definitions[index]
                level = result.get("level") or rule.get("defaultConfiguration", {}).get("level", "warning")
                sev = _severity(rule)
                if level == "error" or (sev is not None and sev >= threshold):
                    failures.append("%s: %s (level=%s, security-severity=%s) at %s" % (
                        path, result.get("ruleId"), level, sev, _location(result)))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sarif", nargs="+", help="SARIF file(s) to gate")
    parser.add_argument("--threshold", type=float, default=4.0,
                        help="minimum security-severity that fails the gate (default 4.0 = medium)")
    args = parser.parse_args(argv)
    if not 0 <= args.threshold <= 4.0:
        print("sarif_gate: threshold must not exceed medium (4.0)", file=sys.stderr)
        return 2
    try:
        failures = gate(args.sarif, args.threshold)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print("sarif_gate: cannot read SARIF: %s" % exc, file=sys.stderr)
        return 2
    if failures:
        print("sarif_gate: %d medium-or-higher finding(s):" % len(failures))
        for line in failures:
            print("  " + line)
        return 1
    print("sarif_gate: no medium-or-higher findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
