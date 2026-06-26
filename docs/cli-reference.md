# CLI reference

```
linkml-data-gen SCHEMA [options]
```

`SCHEMA` is a path or URL to a LinkML schema (YAML). Imports are resolved
relative to the schema file.

## Options

| Flag | Default | Description |
| --- | --- | --- |
| `-o, --output FILE` | stdout | Write generated data here. Progress goes to stderr. |
| `-f, --format {yaml,json}` | `yaml` | Output serialization. |
| `-c, --class NAME` | schema `tree_root` | Root/target class to generate. |
| `-n, --count N` | `5` | Instances per top-level collection (and the list length in `--list`). |
| `--count-for NAME=INT ...` | — | Per-collection or per-class count overrides. |
| `--list` | off | Emit a flat list of `--class` instances instead of a container. |
| `--select TOKEN ...` | all | Generate only collections/classes/modules matching these tokens. |
| `--exclude TOKEN ...` | — | Drop collections/classes/modules matching these tokens. |
| `--with-dependencies` | off | Pull in collections needed to satisfy in-scope references. |
| `--hints FILE` | — | YAML/JSON domain & sampling hints document. |
| `--seed N` | `0` | RNG seed. Use `-1` for nondeterministic output. |
| `--recommended-prob P` | `0.95` | Probability of filling a `recommended` slot. |
| `--optional-prob P` | `0.55` | Probability of filling any other optional slot. |
| `--max-depth N` | `6` | Max recursion depth for inlined nested objects. |
| `--locale NAME` | `en_US` | Faker locale (affects names, addresses, etc.). |
| `--validate` | off | Validate the output against the schema and report. |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (and, with `--validate`, no validation issues). |
| `1` | `--validate` found one or more validation issues. |
| `2` | Usage error (e.g. `--list` without `--class`). |

## Flag details and examples

### `--count` and `--count-for`

`--count` sets the default number of instances per top-level collection.
`--count-for` overrides specific collections (by slot name) or classes (by class
name); a slot-name match wins over a class-name match. Counts are clamped to
`[1, 1000]`.

```bash
# 5 of everything, but 200 donors and 1000 samples:
linkml-data-gen schema/brainbank.yaml -n 5 --count-for donors=200 samples=1000
```

Collections can still grow **beyond** their count when a reference demands a
specific subtype that was not pre-allocated — see
[How it works](how-it-works.md#referential-integrity-and-on-demand-growth).

### `--class` and `--list`

```bash
# One instance of Assay (single-instance mode):
linkml-data-gen schema/brainbank.yaml --class Assay

# A list of 20 SolidSample instances:
linkml-data-gen schema/brainbank.yaml --class SolidSample --list -n 20
```

In `--list` mode there is no container to hold referenced objects, so reference
slots get valid-but-dangling identifier strings. Use container mode for
referentially-complete data.

### `--select`, `--exclude`, `--with-dependencies`

A token matches a **collection slot name**, a **class name**, or a class's
**source module**. See [Selecting part of a schema](scope.md).

```bash
# Only the tissue module (strict — dangling cross-module refs):
linkml-data-gen schema/brainbank.yaml --select tissue

# Tissue, self-contained (referenced donors etc. pulled in):
linkml-data-gen schema/brainbank.yaml --select tissue --with-dependencies

# Everything except two modules:
linkml-data-gen schema/brainbank.yaml --exclude dataset analysis
```

### `--hints`

Load a YAML/JSON document that controls distributions, weighted choices, Faker
providers, cardinality, and population probabilities per slot. See
[Domain hints & distributions](hints.md).

```bash
linkml-data-gen schema/brainbank.yaml --hints examples/brainbank-hints.yaml
```

### `--recommended-prob` / `--optional-prob`

Global probabilities for populating non-required slots. `recommended: true`
slots use `--recommended-prob`; all other optional slots use `--optional-prob`.
Required slots are always populated. Per-slot overrides live in a hints file
(`prob:`).

```bash
# Sparser optional data:
linkml-data-gen schema.yaml --optional-prob 0.2
```

### `--validate`

Validates each generated root object via LinkML's in-process validator and prints
any issues to stderr. Exit code becomes `1` if issues are found.

```bash
linkml-data-gen schema.yaml -o data.yaml --validate
```

## Piping

Data goes to stdout, diagnostics to stderr, so this is safe:

```bash
linkml-data-gen schema.yaml -f json | jq '.donors | length'
```
