# Selecting part of a schema

By default the whole `tree_root` is generated — every collection. To target a
subset (say, only the **tissue** classes of a multi-module schema), use scope
selection.

```bash
linkml-data-gen schema/brainbank.yaml --select tissue -n 10
```

```python
GenerationConfig(select=["tissue"])
GenerationConfig(exclude=["dataset", "analysis"])
GenerationConfig(select=["tissue"], with_dependencies=True)
```

## Tokens match three things

A `--select` / `--exclude` token is matched against, in this order of how you'd
think about it:

1. a **collection slot name** — `samples`, `containers`
2. a **class name** — `Sample`, `Donor`
3. a class's **source module** — the schema file it's defined in, e.g. `tissue`,
   `dataset`, `person`

So all of these are valid:

```bash
linkml-data-gen schema.yaml --select tissue            # a module
linkml-data-gen schema.yaml --select samples containers # collections
linkml-data-gen schema.yaml --select Sample            # a class
```

> Module matching requires the schema to be modular — i.e. classes carry their
> `from_schema` provenance. The generator loads schemas unmerged so this is
> preserved. A single-file schema has just one module (its own name).

## What scope affects

**1. Which top-level collections are generated.** A collection survives if its
slot name, or its range class (hence the family of instances it holds), matches
the selection and isn't excluded.

**2. Which concrete subtypes fill a polymorphic collection.** With `--select
tissue`, the abstract `samples` collection (range `Sample`) is filled only with
tissue-module concretes — `SolidSample`, `LiquidSample` — not subtypes defined in
other modules (like `CNSSection` in the brainbank module). If a selected
collection's range has *no* in-scope concrete, the generator falls back to any
concrete descendant so the collection can still be produced.

## Cross-module references

The interesting case: in-scope data references an out-of-scope class. For
example, tissue's `Sample.donor` is a required reference to `Donor` in the
`person` module. Two policies:

| Mode | Flag | Behavior |
| --- | --- | --- |
| **Strict** (default) | — | The reference becomes a valid-but-dangling id string (e.g. `donor: DNR-0003`) with no `Donor` object present. Truly "this scope and nothing else." Still passes `linkml-validate`, which does no foreign-key checking. |
| **Self-contained** | `--with-dependencies` | The minimum referenced collections are pulled in (donors, and transitively whatever *they* reference) so every reference resolves to a real object. |

How it works under the hood: the *home map* (concrete class → hosting
collection) is built only from in-scope collections in strict mode, so
out-of-scope targets have no home and fall back to a minted dangling id. With
`--with-dependencies`, all collections are eligible homes, so on-demand creation
fills them and they appear in the output.

## Examples

```bash
# Only tissue collections; donor refs are dangling ids:
linkml-data-gen schema/brainbank.yaml --select tissue
#   -> samples, processes, containers, locations

# Tissue, but referentially complete:
linkml-data-gen schema/brainbank.yaml --select tissue --with-dependencies
#   -> samples, processes, containers, locations, donors, cohorts,
#      anatomical_structures, workflow_definitions

# Everything except the dataset/analysis/pathology modules:
linkml-data-gen schema/brainbank.yaml --exclude dataset analysis pathology

# Two specific collections by name:
linkml-data-gen schema/brainbank.yaml --select donors samples
```

## Interaction with counts and hints

Scope composes with everything else: `--count-for`, `--hints`, `--seed`. Counts
apply to whichever collections survive selection; hints resolve normally on the
classes that get generated.

```bash
linkml-data-gen schema/brainbank.yaml \
  --select tissue --with-dependencies \
  --count-for samples=500 \
  --hints examples/brainbank-hints.yaml \
  --seed 1 -o tissue.yaml --validate
```
