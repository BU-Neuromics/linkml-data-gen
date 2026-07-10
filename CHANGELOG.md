# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `mint_id` no longer mints colliding ids for different classes whose names
  share their first 4 capital letters (e.g. `ATACSeqAssay` / `ATACSeqDataset`).
  Class abbreviations are now assigned once and registered globally, growing
  to include more of the class name (and falling back to a numeric suffix)
  whenever a collision would otherwise occur. (#1)

## [0.1.0] - 2026-06-26

Initial release.

### Added

- **Core generator** (`DataGenerator`, `GenerationConfig`) driven entirely by
  `linkml_runtime.SchemaView`.
  - Container mode for `tree_root` schemas with two-phase pooling that guarantees
    referential integrity across (even cyclic) collections.
  - Single-instance and flat-list modes (`generate`, `generate_list`).
  - Polymorphism: abstract collection ranges filled with varied concrete
    subtypes; `designates_type` set to the concrete class name.
  - Unique identifier minting, honoring a `pattern` on the id slot.
  - Scalars by type and slot-name heuristics; regex `pattern` satisfaction;
    numeric bounds; static enums; dynamic (`reachable_from`) enums via synthesized
    CURIEs; timezone-aware datetimes.
  - Fully deterministic output for a fixed seed (fixed date window, isolated RNG).
- **Domain hints & sampling distributions** (`hints.py`: `FieldHint`,
  `HintRegistry`). Per-slot control of distributions (uniform/normal/lognormal/
  exponential/triangular/int), weighted categoricals, fixed choices, Faker
  providers, constants, regexes, date windows, population probability, and
  cardinality (uniform/fixed/poisson). Resolved by selector precedence
  `types < slots < classes`.
- **Schema-scope selection**: `select` / `exclude` by collection name, class
  name, or source module; `with_dependencies` to pull in referenced collections
  for self-contained output, or strict mode with valid-but-dangling references.
- **CLI** (`linkml-data-gen`): YAML/JSON output, `--count`/`--count-for`,
  `--class`/`--list`, `--select`/`--exclude`/`--with-dependencies`, `--hints`,
  `--seed`, probability and depth controls, and `--validate` (in-process).
- **Documentation** under `docs/` (getting started, CLI, Python API, how it
  works, LinkML feature support, hints, scope, recipes, troubleshooting).
- **Tests**: validation-backed suite over a synthetic edge-case schema, a
  two-module schema, and (when present) the real brainbank schema.

[Unreleased]: https://github.com/BU-Neuromics/linkml-data-gen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BU-Neuromics/linkml-data-gen/releases/tag/v0.1.0
