# linkml-data-gen

Generate realistic, stochastic, **schema-valid** test data from *any* [LinkML](https://linkml.io)
schema — from a three-class toy to schemas with hundreds of classes and enums.

Point it at a schema, get back a connected, referentially-consistent dataset suitable for testing,
demos, load-testing, and fixtures. Output validates against the source schema with
`linkml-validate`.

```bash
linkml-data-gen schema/brainbank.yaml -n 10 -o data.yaml --validate
```

## Why

Writing test fixtures by hand for a large LinkML schema is tedious and goes stale as the schema
evolves. This tool derives everything it needs from the schema itself (via
`linkml_runtime.SchemaView`), so the data tracks the schema automatically — including inheritance,
`slot_usage` narrowing, inlining rules, polymorphism, and enums.

## Install

```bash
pip install -e .          # from this repo
# or, in a venv:
python -m venv .venv && .venv/bin/pip install -e .
```

Requires Python ≥ 3.9. Depends on `linkml`, `linkml-runtime`, `faker`, and `rstr`.

## CLI

```bash
linkml-data-gen SCHEMA [options]

  -o, --output FILE        write here (default: stdout)
  -f, --format {yaml,json} output format (default: yaml)
  -c, --class NAME         root/target class (default: the schema's tree_root)
  -n, --count N            instances per top-level collection (default: 5)
      --count-for K=V ...   per-collection/class overrides, e.g. donors=200 samples=1000
      --list               emit a plain list of --class instances (no container)
      --seed N             RNG seed for reproducibility (default: 0; -1 = random)
      --recommended-prob P probability of filling `recommended` slots (default: 0.95)
      --optional-prob P    probability of filling other optional slots (default: 0.55)
      --max-depth N        max recursion depth for inlined nested objects (default: 6)
      --validate           validate the generated output with linkml-validate
```

### Examples

```bash
# A full tree_root container, validated end-to-end:
linkml-data-gen schema/brainbank.yaml -n 8 --validate

# Scale individual collections independently:
linkml-data-gen schema/brainbank.yaml --count-for donors=200 samples=1000 datasets=300 -o big.yaml

# A flat list of one class for unit-testing that class:
linkml-data-gen schema/brainbank.yaml --class SolidSample --list -n 20

# JSON, random each run:
linkml-data-gen schema/model.yaml -f json --seed -1
```

## Python API

```python
from linkml_data_gen import DataGenerator, GenerationConfig

cfg = GenerationConfig(seed=0, default_count=10, count_overrides={"donors": 50})
gen = DataGenerator("schema/brainbank.yaml", cfg)

data = gen.generate()                       # the tree_root container
donors = gen.generate_list("Donor", 25)     # a list of one class
one = gen.generate(root_class="Assay")      # a single instance of any class
```

## What it understands

| LinkML feature | Handling |
| --- | --- |
| `tree_root` | Becomes the output container; its inlined collections are the entity pools. |
| `is_a` / `mixins` | Slots are resolved via `class_induced_slots` (inheritance + `slot_usage`). |
| `abstract` / `mixin` classes | Never instantiated directly; a concrete descendant is chosen instead. |
| Polymorphism | A collection of an abstract range (e.g. `samples: Sample`) is filled with varied concrete subtypes. |
| `designates_type` | The type-designator slot (e.g. `category`) is set to the concrete class name. |
| `identifier` / `key` | Unique ids are minted (honouring a `pattern` on the id slot). |
| Inlined vs. referenced | `SchemaView.is_inlined` decides; references point at real pooled instances by id. |
| `required` / `recommended` | Required always filled; recommended/optional filled probabilistically. |
| `multivalued` | Respects `minimum_cardinality` / `maximum_cardinality`; reference lists are de-duplicated. |
| Scalar types | `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `uri`, `uriorcurie`, derived types. |
| `pattern` | Values are generated to satisfy the regex (via `rstr`). |
| `minimum_value` / `maximum_value` | Numeric bounds respected. |
| Static enums | A permissible value is chosen. |
| Dynamic enums (`reachable_from`) | A plausible CURIE is synthesized from the declared source-node prefix (e.g. `UBERON:0123456`). |
| Slot-name heuristics | `email`, `name`, `description`, `url`, `version`, … get type-appropriate realistic values. |

### Referential integrity

In container mode the generator works in two phases — it allocates every pooled entity (id +
type designator) for all collections **first**, then fills them. Because all targets exist before
any reference is resolved, every reference points at a real instance, even when collections
reference each other cyclically. When a reference needs a specific subtype that wasn't
pre-allocated, one is created on demand and appended to the most specific collection that can host
it (so it still appears in the output).

## Reproducibility

Runs are fully deterministic for a fixed `seed`: the same schema + seed + config always produces
byte-identical output. (Notably, dates/datetimes are drawn from a fixed reference window rather than
"now", so output never depends on wall-clock time.) Use `--seed -1` for nondeterministic output.

## Limitations / not yet handled

These are recognised gaps, not silent ones:

- **Domain semantics.** Values are realistic in *shape* but not in *meaning* — an `age_at_death`
  may be any number within its declared bounds. Add `minimum_value`/`maximum_value`/`pattern` to the
  schema to constrain them.
- **Cross-slot rules.** `rules`, `classification_rules`, `equals_expression`, boolean slot
  expressions (`any_of`/`all_of`/`none_of`), and `unique_keys` beyond identifiers are not enforced.
- **Referential integrity in `--list` mode.** A flat list has no container to hold referenced
  objects, so reference slots get valid-but-dangling id strings.
- **Dynamic enum membership.** Synthesized CURIEs match the ontology prefix but are not checked
  against the live ontology.

## Tests

```bash
pip install -e ".[test]"
pytest
```

The suite validates generated data against both a synthetic edge-case schema (patterns, bounds,
mixins, inlined value objects, references) and — when present as a sibling checkout — the real
`brainbank-hippo-schema`, across many seeds and at scale.
