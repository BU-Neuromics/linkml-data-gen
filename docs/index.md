# linkml-data-gen documentation

Generate realistic, stochastic, **schema-valid** test data from any
[LinkML](https://linkml.io) schema — from a three-class toy to schemas with
hundreds of classes and enums.

```bash
linkml-data-gen schema/brainbank.yaml -n 10 -o data.yaml --validate
```

## Contents

| Guide | What's in it |
| --- | --- |
| [Getting started](getting-started.md) | Install, first run, the three generation modes, reproducibility. |
| [CLI reference](cli-reference.md) | Every flag, with examples and exit codes. |
| [Python API](python-api.md) | `DataGenerator`, `GenerationConfig`, `HintRegistry`, `FieldHint`. |
| [How it works](how-it-works.md) | The generation algorithm: SchemaView-driven, two-phase pooling, references, polymorphism. |
| [LinkML feature support](linkml-feature-support.md) | Exactly how each LinkML construct is handled. |
| [Domain hints & distributions](hints.md) | Full hint format: distributions, weighted choices, Faker, cardinality, dates, probabilities. |
| [Selecting part of a schema](scope.md) | `--select` / `--exclude` / `--with-dependencies`, module/class/collection scoping. |
| [Recipes](recipes.md) | Task-oriented cookbook for common goals. |
| [Limitations & troubleshooting](limitations-and-troubleshooting.md) | Known gaps, error messages, fixes. |

## The 30-second tour

```bash
# Whole tree_root container, validated end-to-end:
linkml-data-gen schema/brainbank.yaml -n 8 --validate

# Scale individual collections:
linkml-data-gen schema/brainbank.yaml --count-for donors=200 samples=1000

# Only the tissue module, self-contained:
linkml-data-gen schema/brainbank.yaml --select tissue --with-dependencies

# Realistic value distributions from a hints file:
linkml-data-gen schema/brainbank.yaml --hints examples/brainbank-hints.yaml

# A flat list of one class:
linkml-data-gen schema/brainbank.yaml --class SolidSample --list -n 20
```

## Design goals

1. **Schema-faithful.** Everything is derived from the schema through
   `linkml_runtime.SchemaView`, so output tracks the schema as it evolves —
   inheritance, `slot_usage`, inlining, polymorphism, and enums included.
2. **Valid by construction.** Output is meant to pass `linkml-validate` against
   the source schema. The test suite enforces this on real and synthetic schemas.
3. **Reproducible.** A fixed `seed` yields byte-identical output, every run.
4. **Scalable.** Bounded output and predictable counts from a handful of
   instances to thousands.
5. **Tunable without forking the schema.** Distributions, domain values, and
   scope are controlled by config/hints, not by editing the schema.
