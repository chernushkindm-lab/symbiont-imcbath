"""JSON command-line interface; invoke as ``python -m symbiont_imcbath``."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import (
    ProfileError, apply_profile, export_model, inspect_reaction, load_baseline,
    model_info, protected_baseline_paths, read_json_document, solve,
)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProfileError(message)


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description="Inspect, edit and simulate the pinned iMcBath model.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    for name in ("info", "inspect", "simulate", "export", "validate-profile", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, help="Write the JSON response to this path instead of stdout")
        if name != "validate-profile":
            command.add_argument("--profile", action="append", default=[], help="Profile path or built-in name; repeat to apply in sequence")
        if name == "inspect":
            command.add_argument("reaction_id")
        elif name == "simulate":
            command.add_argument("--method", choices=("fba", "pfba"), default="pfba")
            command.add_argument("--uptake-cap", action="append", default=[], metavar="REACTION=VALUE", help="Temporary positive exchange cap, mmol/(g modeled biomass h)")
        elif name == "export":
            command.add_argument("destination", type=Path)
            command.add_argument("--format", choices=("json", "sbml"))
            command.add_argument("--force", action="store_true", help="Replace an existing export (immutable upstream files stay protected)")
        elif name == "validate-profile":
            command.add_argument("profile")
        elif name == "replay":
            command.add_argument("input", type=Path)
            command.add_argument("--method", choices=("fba", "pfba"), default="pfba")
    return parser


def _caps(entries: list[str]) -> dict:
    result = {}
    for entry in entries:
        reaction_id, separator, value = entry.partition("=")
        if not separator or not reaction_id:
            raise ProfileError(f"Invalid uptake cap {entry!r}; use REACTION=VALUE")
        if reaction_id in result:
            raise ProfileError(f"Duplicate uptake cap for {reaction_id}")
        try:
            result[reaction_id] = float(value)
        except ValueError as error:
            raise ProfileError(f"Invalid uptake cap value: {entry!r}") from error
    return result


def main(argv: list[str] | None = None) -> int:
    """Return 0 for success, 2 for invalid input, 3 for unsolved simulation."""
    try:
        args = _parser().parse_args(argv)
        if args.command == "export" and args.output:
            destination = args.destination.resolve()
            manifest = destination.with_name(destination.name + ".provenance.json").resolve()
            if args.output.resolve() in {destination, manifest}:
                raise ValueError("JSON response output must be separate from the exported model and provenance manifest")
        model = load_baseline()
        if args.output and args.output.resolve() in protected_baseline_paths(model):
            raise ValueError("Cannot overwrite an immutable upstream baseline file")
        for profile in getattr(args, "profile", []) if args.command != "validate-profile" else []:
            model, _ = apply_profile(model, profile)
        exit_code = 0
        if args.command == "info":
            result = model_info(model)
        elif args.command == "inspect":
            result = inspect_reaction(model, args.reaction_id)
        elif args.command == "simulate":
            result = solve(model, method=args.method, uptake_caps=_caps(args.uptake_cap))
            if result["status"] != "optimal" or not result["numerically_feasible"]:
                exit_code = 3
        elif args.command == "validate-profile":
            model, provenance = apply_profile(model, args.profile)
            result = {"status": "valid", "model": model_info(model), "provenance": provenance}
        elif args.command == "export":
            result = export_model(model, args.destination, format=args.format, overwrite=args.force)
        else:
            from .replay import replay_document
            document = read_json_document(args.input)
            result = replay_document(document, model=model, method=args.method)
            if result["status"] != "completed":
                exit_code = 3
        rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return exit_code
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "error", "error_type": type(error).__name__, "message": str(error)}, allow_nan=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
