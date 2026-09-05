#!/usr/bin/env python3
"""
AegisArchive - Model Context Protocol (MCP) Server
Zero external dependencies (Python 3 standard library only).
Allows MCP-compatible AI agents and IDEs to invoke AegisArchive tools.

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import json
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(REPO_ROOT, "profiles")

def list_profiles():
    profiles = []
    if os.path.isdir(PROFILES_DIR):
        for fname in sorted(os.listdir(PROFILES_DIR)):
            if fname.endswith(".json") and fname != "schema.json":
                p_path = os.path.join(PROFILES_DIR, fname)
                try:
                    with open(p_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        profiles.append({
                            "id": data.get("profile_id", fname[:-5]),
                            "name": data.get("profile_name", fname),
                            "description": data.get("description", ""),
                            "allowed_domains": data.get("target", {}).get("allowed_domains", []),
                            "path": p_path
                        })
                except Exception:
                    continue
    return profiles

def search_cdx(query, cdx_path):
    if not os.path.isfile(cdx_path):
        return {"error": f"CDX file not found: {cdx_path}"}
    matches = []
    query_lower = query.lower()
    with open(cdx_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(" CDX"):
                continue
            parts = line.strip().split()
            if len(parts) >= 11:
                url = parts[2]
                mime = parts[3]
                status = parts[4]
                if query_lower in url.lower() or query_lower in mime.lower():
                    matches.append({
                        "url": url,
                        "mime": mime,
                        "status": status,
                        "length": parts[8],
                        "offset": parts[9],
                        "filename": parts[10]
                    })
    return {"matches": matches, "total_matches": len(matches)}

def handle_tool_call(tool_name, arguments):
    if tool_name == "list_profiles":
        return {"profiles": list_profiles()}

    elif tool_name == "search_archive":
        query = arguments.get("query", "")
        cdx_path = arguments.get("cdx_path", "")
        if not cdx_path:
            # Look in ./archive
            archive_dir = os.path.join(REPO_ROOT, "archive")
            if os.path.isdir(archive_dir):
                cdxs = [os.path.join(archive_dir, f) for f in os.listdir(archive_dir) if f.endswith(".cdx")]
                if cdxs:
                    cdx_path = sorted(cdxs)[-1]
        if not cdx_path or not os.path.isfile(cdx_path):
            return {"error": "No CDX index file specified or found in ./archive."}
        return search_cdx(query, cdx_path)

    elif tool_name == "validate_profile":
        profile_json = arguments.get("profile_json", "{}")
        try:
            data = json.loads(profile_json)
            if not data.get("profile_id"):
                return {"valid": False, "error": "Missing 'profile_id'"}
            if not data.get("target", {}).get("allowed_domains"):
                return {"valid": False, "error": "Missing 'target.allowed_domains'"}
            return {"valid": True, "message": "Profile configuration is valid."}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    return {"error": f"Unknown tool: {tool_name}"}

def handle_request(req):
    """Dispatch one JSON-RPC 2.0 request dict. Returns a response dict, or None for notifications."""
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "aegisarchive-mcp",
                    "version": "1.0.0"
                }
            }
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "list_profiles",
                        "description": "List all available AegisArchive preservation profiles.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "search_archive",
                        "description": "Search local CDX indexes for captured URLs and MIME types.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": { "type": "string", "description": "Keyword or URL substring to search for" },
                                "cdx_path": { "type": "string", "description": "Optional path to .cdx index file" }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "validate_profile",
                        "description": "Validate a JSON profile against the AegisArchive schema.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "profile_json": { "type": "string", "description": "Raw JSON string of the profile" }
                            },
                            "required": ["profile_json"]
                        }
                    }
                ]
            }
        }
    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        tool_result = handle_tool_call(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_result, indent=2)
                    }
                ]
            }
        }
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }

def process_line(line):
    """Handle one raw stdin line. Returns the JSON response text to write, or None for notifications."""
    try:
        req = json.loads(line)
        res = handle_request(req)
        if res is None:
            return None
        return json.dumps(res) + "\n"
    except Exception as e:
        err_res = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}",
                "data": traceback.format_exc()
            }
        }
        return json.dumps(err_res) + "\n"

def main():
    """Stdio JSON-RPC 2.0 loop for Model Context Protocol."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        out = process_line(line)
        if out is not None:
            sys.stdout.write(out)
            sys.stdout.flush()

if __name__ == "__main__":
    main()
