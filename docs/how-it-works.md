# How it works

This page explains the generation algorithm and the design choices behind it.
It's useful both for understanding the output and for extending the tool.

## Everything flows from SchemaView

The generator never parses schema YAML itself. It loads the schema into a
`linkml_runtime.SchemaView` and asks *that* for the resolved view of the model:

- `class_induced_slots(cls)` — the full slot set for a class, with inheritance
  (`is_a`, `mixins`) and `slot_usage` overrides already applied.
- `is_inlined(slot)` — whether a class-ranged slot is inlined (nested object) or
  a reference (identifier string), per LinkML's own rules.
- `get_identifier_slot(cls)`, `class_descendants(cls)`, `class_ancestors(cls)`,
  `all_classes/all_enums/all_types`, etc.

Because the model is read through SchemaView, the generated data automatically
tracks the schema as it changes — there's no second, drifting copy of the rules.

## The three modes

| Mode | Trigger | Shape |
| --- | --- | --- |
| **Container** | the target class has multivalued, inlined, class-ranged slots (typically the `tree_root`) | one object whose collection slots are pools of cross-referenced entities |
| **Single instance** | a target class with no such collections | one fully-populated instance |
| **List** | `generate_list()` / `--list` | a flat list of one class |

The rest of this page is about **container mode**, which is where the
interesting machinery lives.

## Two-phase container generation

The hard problem is referential integrity: `Sample.donor` must point to a
`Donor` that actually exists in the document, even though donors and samples are
separate collections and may reference each other in either order.

The generator solves this in two phases:

1. **Allocate.** For every selected collection, create *shells* — objects that
   carry only their identifier and type designator (`category`) — for all the
   instances that collection will hold. Register each shell's id in a pool keyed
   by its concrete class. This happens for **all** collections before any slot is
   filled.
2. **Fill.** Drain a work queue of shells, populating each one's slots. By the
   time any reference slot is filled, every potential target already exists in a
   pool, so the reference always resolves — even across cyclic collection
   dependencies.

```
Phase A (allocate):   donors:[D1,D2,D3]  samples:[S1,S2,S3,S4]  ...   (ids only)
Phase B (fill):       S1.donor -> pick from {D1,D2,D3}   ✓ always resolvable
```

## References vs. inlined objects

For each class-ranged slot the generator asks `SchemaView.is_inlined`:

- **Inlined** (e.g. a `Mass` value object, or a `tree_root` collection): generate
  a nested object recursively. A `max_depth` guard prevents runaway recursion on
  self-referential inlined ranges; at the cap, only required leaf slots are
  emitted.
- **Reference** (range class has an identifier and isn't inlined): emit an
  identifier string pointing at a pooled instance.

### Referential integrity and on-demand growth

When a reference needs an instance of class `C`:

1. If the pool for `C` (or any concrete descendant) is non-empty, **reuse** an
   existing id. Reuse-by-default keeps collection sizes predictable.
2. Otherwise, **create one on demand** and append it to the most specific
   collection that can host `C` (its *home* collection), then point at it. This is
   why a collection can end up slightly larger than its configured count: a
   required reference demanded a subtype that wasn't pre-allocated.
3. If `C` has no home collection in scope, emit a **valid, dangling identifier**
   string rather than fabricate an out-of-place object.

The *home map* — concrete class → best hosting collection — is computed up front
by walking the `tree_root` collections and choosing, for each class, the
collection whose range is the most specific ancestor.

## Polymorphism

A collection's range is often abstract (`samples: Sample`). The generator picks a
random **concrete** descendant for each instance (`Sample` →
`SolidSample`/`LiquidSample`/…), giving realistic variety, and sets the
`designates_type` slot (`category`) to that concrete class name so LinkML can
round-trip the polymorphic collection. Abstract classes and mixins are never
instantiated directly. (Scope can restrict the candidate subtypes — see
[scope](scope.md).)

## Identifiers

Identifiers are minted uniquely. If the identifier slot declares a `pattern`,
values are generated to satisfy that regex (with a uniqueness retry); otherwise a
readable `PREFIX-0001` style id is minted from the class name.

## Leaf values

Scalar values come from the slot's resolved type, with a layer of realism:

- **Type-driven**: `integer`, `float`, `boolean`, `date`, `datetime`, `uri`,
  `uriorcurie`, and derived types each have an appropriate generator. Numeric
  bounds (`minimum_value`/`maximum_value`) are respected; datetimes are
  timezone-aware (RFC3339).
- **Slot-name heuristics**: a slot named `email`, `name`, `description`, `url`,
  `version`, `city`, … gets a matching Faker value, so labels read naturally.
- **Patterns**: a slot `pattern` is satisfied via `rstr`.
- **Enums**: a permissible value is chosen. **Dynamic enums** (`reachable_from`,
  no static values) get a synthesized CURIE using the prefix of a declared source
  node (e.g. `UBERON:0123456`).

All of this can be overridden per slot with [hints](hints.md).

## Determinism

Every random draw uses one seeded RNG (Faker's instance RNG, plus a seeded
`rstr` for patterns). The generator avoids two classic non-determinism traps:

- It does **not** call the global `Faker.seed()` classmethod (which would mutate
  shared state); it isolates each instance with `seed_instance`.
- Dates/datetimes use a **fixed reference window**, never "now", so output can't
  drift with the wall clock.

Result: identical `(schema, seed, config)` ⇒ byte-identical output.

## Module map (for contributors)

| Module | Responsibility |
| --- | --- |
| `generator.py` | `DataGenerator`: modes, two-phase pooling, references, polymorphism, scope, home map. |
| `values.py` | `ValueFactory`: scalars, slot-name heuristics, patterns, enums, identifier minting, distributions. |
| `hints.py` | `FieldHint` + `HintRegistry`: parse and resolve per-slot hints. |
| `config.py` | `GenerationConfig`: all knobs. |
| `cli.py` | Argument parsing, serialization, `--validate`. |
