# Recipes

Task-oriented snippets. All assume the CLI is installed and `schema.yaml` is your
LinkML schema.

## Generate a small smoke-test fixture

```bash
linkml-data-gen schema.yaml -n 3 -o fixture.yaml --validate
```

## Generate a large load-test dataset

```bash
linkml-data-gen schema.yaml \
  --count-for donors=500 samples=5000 datasets=2000 \
  --seed 1 -o big.yaml
```

Counts are clamped to `[1, 1000]` by default; raise `max_count` via the Python
API (`GenerationConfig(max_count=...)`) for larger single collections.

## Make a stable golden file for tests

Pick a fixed seed and commit the output. Identical `(schema, seed, config)`
reproduces it byte-for-byte.

```bash
linkml-data-gen schema.yaml --seed 0 -o tests/data/golden.yaml --validate
```

## Generate just one module's data

```bash
# Strict (dangling cross-module refs):
linkml-data-gen schema.yaml --select tissue -o tissue.yaml

# Self-contained:
linkml-data-gen schema.yaml --select tissue --with-dependencies -o tissue.yaml
```

See [scope](scope.md).

## Generate everything except a module

```bash
linkml-data-gen schema.yaml --exclude analysis pathology
```

## Generate a flat list of one class (e.g. for a unit test)

```bash
linkml-data-gen schema.yaml --class SolidSample --list -n 25 -o samples.yaml
```

## Make values domain-realistic

Create `hints.yaml` (see [hints](hints.md)) and pass it:

```yaml
slots:
  sex: {choices: {male: 55, female: 45}}
classes:
  Donor:
    age_at_death: {distribution: normal, params: {mean: 68, std: 12},
                   minimum: 21, maximum: 102, integer: true}
```

```bash
linkml-data-gen schema.yaml --hints hints.yaml -n 50 --validate
```

## Produce JSON instead of YAML

```bash
linkml-data-gen schema.yaml -f json -o data.json
```

## Generate sparser (or denser) optional data

```bash
linkml-data-gen schema.yaml --optional-prob 0.2    # sparse
linkml-data-gen schema.yaml --optional-prob 0.9    # dense
```

## Pin specific values

```yaml
# hints.yaml
slots:
  status: {const: active}
  data_location: {faker: url}
classes:
  Donor:
    species: {const: "NCBITaxon:9606"}   # always Homo sapiens
```

## Different counts and shape per class, in Python

```python
from linkml_data_gen import DataGenerator, GenerationConfig

cfg = GenerationConfig(
    seed=7,
    count_overrides={"donors": 50, "samples": 300},
    hints={"classes": {"Donor": {"age_at_death": {
        "distribution": "normal", "params": {"mean": 68, "std": 12}}}}},
)
data = DataGenerator("schema.yaml", cfg).generate()
```

## Generate, validate, and inspect in one pipeline

```bash
linkml-data-gen schema.yaml -f json --validate | jq '.samples | length'
```

## Use a non-US locale for names/addresses

```bash
linkml-data-gen schema.yaml --locale de_DE
```
