# linkml-data-gen

Generate realistic, stochastic, **schema-valid** test data from *any* [LinkML](https://linkml.io)
schema — from a three-class toy to schemas with hundreds of classes and enums.

Point it at a schema, get back a connected, referentially-consistent dataset suitable for testing,
demos, load-testing, and fixtures. Output validates against the source schema with
`linkml-validate`.

```bash
linkml-data-gen schema/brainbank.yaml -n 10 -o data.yaml --validate
```

## Documentation

Full guides live in [`docs/`](docs/index.md):

- [Getting started](docs/getting-started.md) · [CLI reference](docs/cli-reference.md) · [Python API](docs/python-api.md)
- [How it works](docs/how-it-works.md) · [LinkML feature support](docs/linkml-feature-support.md)
- [Domain hints & distributions](docs/hints.md) · [Selecting part of a schema](docs/scope.md)
- [Recipes](docs/recipes.md) · [Limitations & troubleshooting](docs/limitations-and-troubleshooting.md)

This README is a concise overview; the docs go deeper.

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
      --select TOKEN ...   generate only these collections/classes/modules (see below)
      --exclude TOKEN ...  drop these collections/classes/modules
      --with-dependencies  pull in collections needed to satisfy in-scope references
      --hints FILE         YAML/JSON domain + sampling hints (see below)
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

## Selecting part of a schema

By default the whole `tree_root` is generated. To target a subset — say, only the
**tissue** classes of a multi-module schema — use `--select` / `--exclude`. A token
matches a collection slot name, a class name, **or a source module** (the schema
file a class is defined in), so you can think in whichever terms fit:

```bash
# Only the tissue module's collections (samples, processes, containers, locations):
linkml-data-gen schema/brainbank.yaml --select tissue -n 10

# Everything except the dataset and analysis modules:
linkml-data-gen schema/brainbank.yaml --exclude dataset analysis

# A specific collection by name:
linkml-data-gen schema/brainbank.yaml --select samples containers
```

Scope also restricts which concrete subtypes fill a polymorphic collection — with
`--select tissue`, the abstract `samples` collection is filled only with
tissue-module concretes (`SolidSample`, `LiquidSample`), not subtypes defined in
other modules.

**Cross-module references.** When in-scope data references an out-of-scope class
(e.g. tissue's `Sample.donor → Donor` in the person module), the default is to
emit a valid-but-dangling id string — truly "this module and nothing else"
(still passes `linkml-validate`, which does no foreign-key checking). Pass
`--with-dependencies` to instead pull in the minimum referenced collections so the
dataset is self-contained and referentially complete.

## Domain hints & sampling distributions

The schema fixes the *shape* of a value (type, bounds, enum) but rarely its
*distribution* or domain meaning. A **hints** file injects that knowledge without
touching the schema — control distributions, weighted categoricals, fixed choice
lists, Faker providers, constants, date windows, population probability, and
cardinality, per slot.

```bash
linkml-data-gen schema/brainbank.yaml --hints examples/brainbank-hints.yaml -n 20 --validate
```

A hints document has three selector scopes, resolved least → most specific
(`types[range]` < `slots[name]` < `classes[Class][slot]`), so a specific rule
overrides a general one key-by-key:

```yaml
types:                                   # defaults by range type
  datetime: {date_start: "2018-01-01", date_end: "2024-12-31"}
slots:                                   # by slot name (any class)
  sex:  {choices: {male: 55, female: 43, unknown: 2}}   # weighted categorical
  name: {faker: catch_phrase}                           # any Faker provider
  description: {prob: 0.3}                               # populate 30% of the time
classes:                                 # by Class.slot (most specific)
  Donor:
    age_at_death:
      distribution: normal               # uniform | normal | lognormal | exponential | triangular | int
      params: {mean: 68, std: 13}
      minimum: 21
      maximum: 102
      integer: true
    cohort:
      cardinality: {min: 1, max: 3, dist: poisson, lam: 1.2}   # uniform | fixed | poisson
  File:
    size_bytes: {distribution: int, minimum: 1_000_000, maximum: 50_000_000_000}
```

Per-slot hint keys: `const`, `choices` (list, or `{value: weight}` map), `weights`,
`faker` (+ `faker_args` / `faker_kwargs`), `pattern`, `distribution` (+ `params`,
`minimum`, `maximum`, `integer`), `date_start` / `date_end`, `prob`, and
`cardinality` (`{min, max, dist, lam}`). Out-of-bounds distribution draws are
resampled, then clamped. All sampling uses the seeded RNG, so hinted runs stay
reproducible. `prob` only affects non-required slots — required slots are always
populated to preserve validity.

The Python API takes the same document as a dict:

```python
cfg = GenerationConfig(seed=0, hints={
    "slots": {"sex": {"choices": {"male": 55, "female": 45}}},
    "classes": {"Donor": {"age_at_death": {"distribution": "normal",
                                           "params": {"mean": 68, "std": 12}}}},
})
DataGenerator("schema/brainbank.yaml", cfg).generate()
```

## Reproducibility

Runs are fully deterministic for a fixed `seed`: the same schema + seed + config always produces
byte-identical output. (Notably, dates/datetimes are drawn from a fixed reference window rather than
"now", so output never depends on wall-clock time.) Use `--seed -1` for nondeterministic output.

## Limitations / not yet handled

These are recognised gaps, not silent ones:

- **Domain semantics.** Without hints, values are realistic in *shape* but not *meaning* — an
  `age_at_death` may be any number within its declared bounds. Use a [hints file](#domain-hints--sampling-distributions)
  (or add `minimum_value`/`maximum_value`/`pattern` to the schema) to give values realistic
  distributions and domain meaning.
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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, testing,
and the PR process, and note our [Code of Conduct](CODE_OF_CONDUCT.md). Use the issue templates to
[report a bug or request a feature](.github/ISSUE_TEMPLATE). Security issues: see
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © BU Neuromics. If you use this in published work, citation metadata is in
[CITATION.cff](CITATION.cff). Release notes live in [CHANGELOG.md](CHANGELOG.md).
