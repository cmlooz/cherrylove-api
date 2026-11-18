"""Contract release assets in YAML and JSON with the same content (ADR-003 §3, DEC-044).

python scripts/contract_json.py export contract/openapi.v1.yaml openapi.v1.json
python scripts/contract_json.py check  contract/openapi.v1.yaml openapi.v1.json
python scripts/contract_json.py version contract/openapi.v1.yaml      # prints info.version
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml


class _StringDatesLoader(yaml.SafeLoader):
    """YAML 1.1 would turn `2026-10-31` into a date; JSON has no dates, so keep every scalar as written."""


_StringDatesLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_StringDatesLoader)  # noqa: S506 - SafeLoader subclass


def export(source: Path, target: Path) -> None:
    text = json.dumps(load_yaml(source), ensure_ascii=False, indent=2) + "\n"
    target.write_text(text, encoding="utf-8", newline="\n")


def same_content(yaml_path: Path, json_path: Path) -> bool:
    parsed_json: Any = json.loads(json_path.read_text(encoding="utf-8"))
    return bool(load_yaml(yaml_path) == parsed_json)


def version(source: Path) -> str:
    value = load_yaml(source)["info"]["version"]
    return str(value)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["export", "check", "version"])
    parser.add_argument("yaml_path", type=Path)
    parser.add_argument("json_path", type=Path, nargs="?")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "version":
        print(version(args.yaml_path))
        return 0
    if args.json_path is None:
        parser.error(f"{args.command} needs a JSON path")
    if args.command == "export":
        export(args.yaml_path, args.json_path)
        return 0
    if same_content(args.yaml_path, args.json_path):
        return 0
    print("contract-json: YAML and JSON assets differ", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
