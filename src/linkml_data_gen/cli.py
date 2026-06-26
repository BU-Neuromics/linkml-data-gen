"""Command-line interface for linkml-data-gen."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from linkml_runtime import SchemaView

from .config import GenerationConfig
from .generator import DataGenerator


def _parse_counts(pairs: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in pairs:
        if "=" not in p:
            raise argparse.ArgumentTypeError(f"--count-for expects NAME=INT, got {p!r}")
        k, v = p.split("=", 1)
        out[k.strip()] = int(v)
    return out


def _dump(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, indent=2, default=str)
    import yaml  # linkml pulls in PyYAML

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="linkml-data-gen",
        description="Generate realistic, stochastic, schema-valid test data from a LinkML schema.",
    )
    p.add_argument("schema", help="Path or URL to the LinkML schema (YAML).")
    p.add_argument("-o", "--output", help="Output file (default: stdout).")
    p.add_argument("-f", "--format", choices=["yaml", "json"], default="yaml")
    p.add_argument(
        "-c", "--class", dest="root_class",
        help="Root/target class. Defaults to the schema's tree_root.",
    )
    p.add_argument(
        "-n", "--count", type=int, default=5,
        help="Default number of instances per top-level collection (default: 5).",
    )
    p.add_argument(
        "--count-for", nargs="*", default=[], metavar="NAME=INT",
        help="Per-collection or per-class count override, e.g. --count-for donors=20 samples=100.",
    )
    p.add_argument(
        "--list", action="store_true",
        help="Emit a plain list of --class instances instead of a container/root object.",
    )
    p.add_argument(
        "--hints", metavar="FILE",
        help="YAML/JSON file of domain/sampling hints (distributions, choices, "
             "weights, faker providers, cardinality, population probabilities).",
    )
    p.add_argument("--seed", type=int, default=0, help="RNG seed (default: 0; use -1 for random).")
    p.add_argument("--recommended-prob", type=float, default=0.95)
    p.add_argument("--optional-prob", type=float, default=0.55)
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--locale", default="en_US")
    p.add_argument(
        "--validate", action="store_true",
        help="After generating, validate the output with linkml-validate and report.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    hints = None
    if args.hints:
        import yaml

        with open(args.hints) as fh:
            hints = yaml.safe_load(fh)

    config = GenerationConfig(
        seed=None if args.seed == -1 else args.seed,
        default_count=args.count,
        count_overrides=_parse_counts(args.count_for),
        recommended_prob=args.recommended_prob,
        optional_prob=args.optional_prob,
        max_depth=args.max_depth,
        locale=args.locale,
        hints=hints,
    )

    sv = SchemaView(args.schema)
    gen = DataGenerator(sv, config)

    if args.list:
        if not args.root_class:
            print("--list requires --class CLASSNAME", file=sys.stderr)
            return 2
        data = gen.generate_list(args.root_class, args.count)
        root_class = args.root_class
    else:
        data = gen.generate(args.root_class)
        root_class = args.root_class or gen.tree_root

    text = _dump(data, args.format)

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    if args.validate:
        return _validate(args, root_class, data)
    return 0


def _validate(args, root_class: str | None, data: Any) -> int:
    """Validate the generated data against its schema via the LinkML API.

    Uses the in-process validator (no dependency on a ``linkml-validate`` binary
    on PATH) and resolves relative imports from the schema's own directory.
    """
    import contextlib
    import os
    from pathlib import Path

    from linkml.validator import validate

    schema_path = Path(args.schema)

    @contextlib.contextmanager
    def _in_dir(path):
        prev = os.getcwd()
        if path:
            os.chdir(path)
        try:
            yield
        finally:
            os.chdir(prev)

    instances = data if isinstance(data, list) else [data]
    parent = str(schema_path.parent) if schema_path.parent != Path("") else None
    schema_arg = schema_path.name if parent else args.schema

    total = 0
    with _in_dir(parent):
        for inst in instances:
            report = validate(inst, schema_arg, root_class)
            for r in report.results:
                print(f"[validate] {r.severity} {r.message}", file=sys.stderr)
                total += 1
    if total == 0:
        print("[validate] OK — no issues found", file=sys.stderr)
        return 0
    print(f"[validate] {total} issue(s) found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
