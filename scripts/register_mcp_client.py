#!/usr/bin/env python3
"""Register Emotion Engine with local MCP-capable clients."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


SERVER_NAME = "emotion-engine"


def resolved(path):
    return Path(path).expanduser().resolve()


def package_dir():
    return Path(__file__).resolve().parents[1]


def default_server_script(project_dir, package_root):
    project_sidecar = (
        project_dir
        / ".codex"
        / "skills"
        / "emotion-engine-codex"
        / "scripts"
        / "emotion_engine_mcp.py"
    )
    if project_sidecar.exists():
        return project_sidecar

    packaged = package_root / "scripts" / "emotion_engine_mcp.py"
    if packaged.exists():
        return packaged

    raise SystemExit("Could not find emotion_engine_mcp.py. Pass --server-script explicitly.")


def default_state_file(project_dir, state_profile):
    if state_profile == "codex":
        return project_dir / ".emotion-engine" / "codex-state.json"
    if state_profile == "generic":
        return project_dir / ".emotion-engine" / "emotion-state.json"

    codex_sidecar = project_dir / ".codex" / "skills" / "emotion-engine-codex"
    if (project_dir / ".codex").exists() or codex_sidecar.exists():
        return project_dir / ".emotion-engine" / "codex-state.json"
    return project_dir / ".emotion-engine" / "emotion-state.json"


def mcp_entry(python_bin, server_script, state_file):
    return {
        "command": python_bin,
        "args": [os.fspath(server_script), "--state", os.fspath(state_file)],
    }


def load_json_object(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def write_mcp_json(path, name, python_bin, server_script, state_file, dry_run):
    data = load_json_object(path)
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise SystemExit(f"{path} has non-object mcpServers")
    servers[name] = mcp_entry(python_bin, server_script, state_file)
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"Would write {path}:")
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"Updated {path}")


def codex_command(name, python_bin, server_script, state_file):
    return [
        "codex",
        "mcp",
        "add",
        name,
        "--",
        python_bin,
        os.fspath(server_script),
        "--state",
        os.fspath(state_file),
    ]


def claude_code_command(name, python_bin, server_script, state_file):
    return [
        "claude",
        "mcp",
        "add",
        "--transport",
        "stdio",
        name,
        "--",
        python_bin,
        os.fspath(server_script),
        "--state",
        os.fspath(state_file),
    ]


def run_command(command, dry_run):
    printable = " ".join(shlex.quote(part) for part in command)
    if dry_run:
        print(printable)
        return
    subprocess.run(command, check=True)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "client",
        choices=["codex", "claude-code", "mcp-json", "all"],
        help="client config to write or command to run",
    )
    parser.add_argument("--name", default=SERVER_NAME, help="MCP server name")
    parser.add_argument("--project-dir", default=os.getcwd(), help="project directory for state/config")
    parser.add_argument("--server-script", help="path to emotion_engine_mcp.py")
    parser.add_argument("--state-file", help="path to the Emotion Engine state file")
    parser.add_argument(
        "--state-profile",
        choices=["auto", "codex", "generic"],
        default="auto",
        help="default state path profile when --state-file is omitted",
    )
    parser.add_argument("--python", default=os.environ.get("PYTHON", "python3"), help="Python executable")
    parser.add_argument("--mcp-json", help="path to .mcp.json; defaults to <project-dir>/.mcp.json")
    parser.add_argument("--dry-run", action="store_true", help="print the change without applying it")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    project_dir = resolved(args.project_dir)
    if not project_dir.is_dir():
        raise SystemExit(f"Project directory does not exist: {project_dir}")
    package_root = package_dir()
    server_script = resolved(args.server_script) if args.server_script else default_server_script(project_dir, package_root)
    state_file = resolved(args.state_file) if args.state_file else default_state_file(project_dir, args.state_profile)
    mcp_json_path = resolved(args.mcp_json) if args.mcp_json else project_dir / ".mcp.json"

    if not args.dry_run:
        state_file.parent.mkdir(parents=True, exist_ok=True)

    if args.client in {"codex", "all"}:
        run_command(codex_command(args.name, args.python, server_script, state_file), args.dry_run)
    if args.client in {"claude-code", "all"}:
        run_command(claude_code_command(args.name, args.python, server_script, state_file), args.dry_run)
    if args.client in {"mcp-json", "all"}:
        write_mcp_json(mcp_json_path, args.name, args.python, server_script, state_file, args.dry_run)


if __name__ == "__main__":
    main(sys.argv[1:])
