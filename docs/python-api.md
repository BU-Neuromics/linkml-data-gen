# Python API

Everything the CLI does is available programmatically.

```python
from linkml_data_gen import DataGenerator, GenerationConfig
```

## `DataGenerator`

```python
DataGenerator(schema, config=None)
```

| Argument | Type | Notes |
| --- | --- | --- |
| `schema` | `str` \| `SchemaView` | A path/URL to a schema, or a pre-built `linkml_runtime.SchemaView`. |
| `config` | `GenerationConfig` \| `None` | Generation settings; defaults are used if omitted. |

> Pass a path (or an **unmerged** `SchemaView`) so per-class module provenance is
> preserved — module-based [scope selection](scope.md) relies on it. The
> generator constructs `SchemaView(schema)` (no `merge_imports`) when given a
> string.

### Methods

#### `generate(root_class=None) -> dict`

Generate the root object. With a `tree_root` (or any class that has inlined
collection slots) this returns a populated container `dict`; otherwise it returns
a single instance `dict`.

```python
gen = DataGenerator("schema/brainbank.yaml", GenerationConfig(seed=0))
data = gen.generate()                  # the BrainBank tree_root container
one  = gen.generate(root_class="Assay")  # a single Assay instance
```

Raises `ValueError` if the schema has no `tree_root` and no `root_class` is given,
or if `root_class` is unknown.

#### `generate_list(class_name, count=None) -> list`

Generate a flat list of independent instances of one class.

```python
donors = gen.generate_list("Donor", 25)
```

References inside list-mode instances are valid-but-dangling id strings (there is
no container to hold their targets).

#### `tree_root` (property) -> `str | None`

The name of the schema's `tree_root` class, or `None`.

## `GenerationConfig`

A dataclass of generation settings. All fields are optional.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `seed` | `int \| None` | `0` | RNG seed; `None` = nondeterministic. |
| `default_count` | `int` | `5` | Instances per top-level collection. |
| `min_count` | `int` | `1` | Lower clamp for resolved counts. |
| `max_count` | `int` | `1000` | Upper clamp for resolved counts. |
| `count_overrides` | `dict[str,int]` | `{}` | Per-collection (slot name) or per-class counts. |
| `recommended_prob` | `float` | `0.95` | Fill probability for `recommended` slots. |
| `optional_prob` | `float` | `0.55` | Fill probability for other optional slots. |
| `multivalued_min` | `int` | `1` | Default min items for multivalued slots. |
| `multivalued_max` | `int` | `4` | Default max items for multivalued slots. |
| `max_depth` | `int` | `6` | Max inline-recursion depth. |
| `locale` | `str` | `"en_US"` | Faker locale. |
| `hints` | `dict \| HintRegistry \| None` | `None` | Domain/sampling hints ([format](hints.md)). |
| `select` | `list \| None` | `None` | Scope tokens to keep ([scope](scope.md)). |
| `exclude` | `list \| None` | `None` | Scope tokens to drop. |
| `with_dependencies` | `bool` | `False` | Pull in referenced out-of-scope collections. |

`count_for(slot_name, class_name=None)` resolves the effective count for a
collection, honoring overrides and clamps.

### Examples

```python
# Scale, sparsity, and reproducibility:
cfg = GenerationConfig(
    seed=7,
    default_count=10,
    count_overrides={"donors": 50, "samples": 300},
    optional_prob=0.3,
)
data = DataGenerator("schema/brainbank.yaml", cfg).generate()

# Scope to one module, self-contained:
cfg = GenerationConfig(seed=0, select=["tissue"], with_dependencies=True)
tissue = DataGenerator("schema/brainbank.yaml", cfg).generate()

# Domain hints (same document shape as the --hints file):
cfg = GenerationConfig(seed=0, hints={
    "slots": {"sex": {"choices": {"male": 55, "female": 45}}},
    "classes": {"Donor": {"age_at_death": {
        "distribution": "normal", "params": {"mean": 68, "std": 12},
        "minimum": 21, "maximum": 102, "integer": True}}},
})
data = DataGenerator("schema/brainbank.yaml", cfg).generate()
```

## Serializing the result

`generate()` / `generate_list()` return plain Python `dict`/`list` structures
(strings, numbers, booleans, nested dicts/lists), ready for `yaml.safe_dump` or
`json.dumps`.

```python
import yaml
print(yaml.safe_dump(data, sort_keys=False))
```

## Validating programmatically

```python
import os, contextlib
from pathlib import Path
from linkml.validator import validate

def assert_valid(data, schema_path, target_class):
    schema_path = Path(schema_path)
    prev = os.getcwd()
    os.chdir(schema_path.parent)          # resolve relative imports
    try:
        report = validate(data, schema_path.name, target_class)
    finally:
        os.chdir(prev)
    assert not report.results, [r.message for r in report.results]
```

## Hints internals: `HintRegistry` and `FieldHint`

Lower-level building blocks in `linkml_data_gen.hints`:

```python
from linkml_data_gen.hints import HintRegistry, FieldHint

reg = HintRegistry({
    "types": {"float": {"minimum": 0, "maximum": 1}},
    "slots": {"weight_g": {"minimum": 5}},
    "classes": {"Widget": {"weight_g": {"maximum": 50}}},
})
hint = reg.for_slot("Widget", "weight_g", "float")   # merged FieldHint
```

`HintRegistry.for_slot(class_name, slot_name, range_name)` resolves the merged
hint for a slot (precedence: `types[range]` < `slots[name]` <
`classes[Class][slot]`). You normally just pass the document as
`GenerationConfig(hints=...)` and let the generator handle resolution. See the
[hints reference](hints.md) for every field.
