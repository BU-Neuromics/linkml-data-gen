# Domain hints & sampling distributions

A schema fixes the *shape* of a value (its type, bounds, enum) but rarely its
*distribution* or domain meaning. A **hints** document injects that knowledge
without editing the schema: distributions, weighted categoricals, fixed choice
lists, Faker providers, constants, regexes, date windows, population
probability, and cardinality — all per slot.

```bash
linkml-data-gen schema/brainbank.yaml --hints examples/brainbank-hints.yaml -n 20 --validate
```

```python
GenerationConfig(hints={...})   # same document, as a dict
```

All hinted sampling uses the seeded RNG, so hinted runs stay fully reproducible.

## Document structure

Three selector scopes, resolved **least → most specific**, merged key-by-key:

```
types[range]   <   slots[name]   <   classes[Class][slot]
```

```yaml
types:                       # defaults by range type
  datetime: {date_start: "2018-01-01", date_end: "2024-12-31"}

slots:                       # by slot name, any class
  sex:  {choices: {male: 55, female: 43, unknown: 2}}
  name: {faker: catch_phrase}
  description: {prob: 0.3}

classes:                     # by Class.slot (wins)
  Donor:
    age_at_death:
      distribution: normal
      params: {mean: 68, std: 13}
      minimum: 21
      maximum: 102
      integer: true
    cohort:
      cardinality: {min: 1, max: 3, dist: poisson, lam: 1.2}
```

A convenience flat form is also accepted at the top level: a key containing a dot
is treated as `Class.slot`, and a dotless key as a slot name.

```yaml
"Donor.age_at_death": {distribution: normal, params: {mean: 68, std: 13}}
sex: {choices: [male, female]}
```

## Hint keys

A hint for one slot may set any of these. They're checked roughly in this order;
the first applicable one wins for value shaping.

### Value shaping

| Key | Type | Effect |
| --- | --- | --- |
| `const` | any | Always emit this exact value. |
| `choices` | list, or `{value: weight}` map | Pick from this set. A map sets `weights` automatically. |
| `weights` | list | Weights parallel to `choices` (or to an enum's permissible values). |
| `faker` | string | Call this Faker provider, e.g. `name`, `company`, `ssn`, `catch_phrase`. |
| `faker_args` | list | Positional args for the Faker provider. |
| `faker_kwargs` | map | Keyword args for the Faker provider. |
| `pattern` | regex | Generate a value matching this regex (overrides any schema pattern). |

### Numeric distribution

| Key | Type | Effect |
| --- | --- | --- |
| `distribution` (alias `dist`) | string | One of `uniform`, `normal`/`gaussian`, `lognormal`, `exponential`, `triangular`, `int`/`int_uniform`. |
| `params` | map | Distribution parameters (see table below). |
| `minimum` (alias `min`) | number | Lower bound; out-of-bounds draws are resampled, then clamped. |
| `maximum` (alias `max`) | number | Upper bound. |
| `integer` | bool | Round the result to an integer. |

Distribution parameters:

| `distribution` | `params` keys | Notes |
| --- | --- | --- |
| `uniform` | — | Uniform over `[minimum, maximum]`. |
| `normal` | `mean` (`mu`), `std` (`sigma`) | Gaussian; resampled to stay within bounds. |
| `lognormal` | `mean` (`mu`), `sigma` (`std`) | Right-skewed, positive. |
| `exponential` | `lam` (`rate`) | Mean = 1/lam. |
| `triangular` | `mode` | Over `[minimum, maximum]` with a peak at `mode`. |
| `int` | — | Uniform integer over `[minimum, maximum]`. |

A bounds-only hint (no `distribution`) just narrows the default uniform range:

```yaml
classes:
  File:
    size_bytes: {minimum: 1000000, maximum: 50000000000}
```

### Dates

| Key | Type | Effect |
| --- | --- | --- |
| `date_start` | ISO date/datetime | Window start for `date`/`datetime` slots. |
| `date_end` | ISO date/datetime | Window end. |

Use ISO strings for deterministic windows.

### Slot behavior

| Key | Type | Effect |
| --- | --- | --- |
| `prob` | float 0–1 | Probability of populating this slot. **Non-required slots only** — required slots are always populated to preserve validity. |
| `cardinality` | map | For multivalued slots: `{min, max, dist, lam}`. |

Cardinality distributions (`dist`): `uniform` (default), `fixed` (always `max`),
`poisson` (`lam` ≈ mean, clamped to `[min, max]`).

## Worked examples

### Weighted categorical + Faker label

```yaml
slots:
  sex:  {choices: {male: 55, female: 43, unknown: 2}}
  name: {faker: catch_phrase}
```

### Realistic ages (bounded normal, integer)

```yaml
classes:
  Donor:
    age_at_death:
      distribution: normal
      params: {mean: 68, std: 13}
      minimum: 21
      maximum: 102
      integer: true
```

### Right-skewed durations (lognormal)

```yaml
classes:
  Donor:
    post_mortem_interval_hours:
      distribution: lognormal
      params: {mean: 2.6, sigma: 0.5}   # median ~13.5h
      maximum: 96
```

### Constant + restricted choices on enums and references

```yaml
slots:
  status: {choices: [active]}     # always "active"
  read_length: {choices: [50, 75, 100, 150], weights: [1, 2, 4, 8]}
classes:
  Widget:
    created_by: {const: system}
    owner: {prob: 0.0}            # never populate this optional reference
```

### Cardinality control

```yaml
classes:
  Donor:
    cohort: {cardinality: {min: 1, max: 3, dist: poisson, lam: 1.2}}
  FileSet:
    files: {cardinality: {min: 2, max: 2, dist: fixed}}   # always 2
```

## Precedence example

```yaml
types:   {float: {minimum: 0, maximum: 1}}
slots:   {weight_g: {minimum: 5}}
classes: {Widget: {weight_g: {maximum: 50}}}
```

For `Widget.weight_g` (a float): `minimum` resolves to `5` (slot over type) and
`maximum` to `50` (class.slot over type) → uniform over `[5, 50]`. A different
float slot with no other hint inherits `[0, 1]` from the type default.

## Behavior notes

- Out-of-bounds distribution draws are resampled up to 100 times, then clamped to
  the bounds — so a hint can never emit a value outside `[minimum, maximum]`.
- A `const`/`choices`/`faker` hint can stand in even for a class-ranged
  (reference) slot, letting you pin specific ids or codes.
- Everything is seeded; see [How it works → Determinism](how-it-works.md#determinism).

See the full example: [`examples/brainbank-hints.yaml`](../examples/brainbank-hints.yaml)
and its output [`examples/brainbank-hinted.yaml`](../examples/brainbank-hinted.yaml).
