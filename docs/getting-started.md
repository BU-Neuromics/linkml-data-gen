# Getting started

## Install

`linkml-data-gen` needs Python ≥ 3.9. Installing from the repo gives you both
the `linkml-data-gen` CLI and the `linkml_data_gen` Python package.

```bash
# In a virtual environment (recommended):
python -m venv .venv
.venv/bin/pip install -e .

# With test dependencies:
.venv/bin/pip install -e ".[test]"
```

Dependencies (installed automatically): `linkml`, `linkml-runtime`, `faker`,
`rstr`, `pyyaml`.

> **Note on environments with a patched system `pip`:** some distributions ship a
> `setuptools` that fails to build certain LinkML dependencies. A clean
> `venv` (as above) avoids this.

## Your first dataset

Point the CLI at any LinkML schema:

```bash
linkml-data-gen path/to/schema.yaml -n 5 -o data.yaml
```

If the schema declares a `tree_root` class, you get a populated container object.
Add `--validate` to immediately check the result against the schema:

```bash
linkml-data-gen path/to/schema.yaml -n 5 -o data.yaml --validate
# ...
# [validate] OK — no issues found
```

`--validate` runs LinkML's in-process validator (no `linkml-validate` binary
needed on your `PATH`) and resolves the schema's relative imports from the
schema's own directory.

## The three generation modes

| Mode | How to invoke | Output |
| --- | --- | --- |
| **Container** | default, when the target class has inlined collection slots (typically the `tree_root`) | one container object holding cross-referenced pools of entities |
| **Single instance** | `--class SomeClass` where the class has no collections | one fully-populated instance |
| **List** | `--class SomeClass --list -n N` | a flat list of `N` instances of that class |

Container mode is the realistic one: it builds a connected graph where, e.g.,
`samples` reference `donors` that actually exist in the same document. See
[How it works](how-it-works.md).

```bash
# Container (default — uses the schema's tree_root):
linkml-data-gen schema/brainbank.yaml

# A single instance of a specific class:
linkml-data-gen schema/brainbank.yaml --class Assay

# 20 standalone instances of a class:
linkml-data-gen schema/brainbank.yaml --class SolidSample --list -n 20
```

## Reproducibility

Runs are deterministic for a fixed seed: the same `(schema, seed, config)` always
produces byte-identical output.

```bash
linkml-data-gen schema.yaml --seed 42      # repeatable
linkml-data-gen schema.yaml --seed -1      # nondeterministic (fresh each run)
```

Dates and datetimes are drawn from a fixed reference window rather than "now", so
output never depends on the wall clock — a subtle but important property for
golden-file tests.

## Output format

YAML by default; `--format json` for JSON.

```bash
linkml-data-gen schema.yaml -f json -o data.json
```

Without `-o`, the data is written to stdout (progress/validation messages go to
stderr, so you can pipe the data cleanly).

## Next steps

- [CLI reference](cli-reference.md) — all the flags.
- [Domain hints & distributions](hints.md) — make values domain-realistic.
- [Selecting part of a schema](scope.md) — generate only the modules you want.
