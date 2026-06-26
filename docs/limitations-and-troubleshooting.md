# Limitations & troubleshooting

## Known limitations

These are recognized gaps, not silent ones.

### Domain semantics

Without [hints](hints.md), values are realistic in *shape* but not *meaning* — an
`age_at_death` can be any number within its declared bounds, a `name` is a random
phrase. Use a hints file (or tighten the schema with
`minimum_value`/`maximum_value`/`pattern`) to give values real distributions and
meaning.

### Cross-slot constraints are not enforced

The generator fills slots independently. It does **not** evaluate:

- `rules` / `classification_rules`
- boolean slot expressions (`any_of`, `all_of`, `none_of`, `exactly_one_of`)
- `equals_expression`, `string_serialization`
- `unique_keys` beyond the `identifier` slot
- `ifabsent` defaults

If your schema relies on these for validity, generated data may need
post-processing, or the constraints may need to be expressible as per-slot facts
(bounds, patterns, enums) that the generator *does* honor.

### Referential integrity only in container mode

Container mode (the `tree_root`) produces a connected, referentially-complete
graph. In `--list` and single-instance mode there is no container to host
referenced objects, so reference slots get valid-but-dangling id strings. The
same is true for cross-scope references in strict [scope](scope.md) mode (by
design); use `--with-dependencies` for self-contained output.

### Dynamic enum membership

For `reachable_from` enums, a CURIE is synthesized from the declared source-node
prefix (e.g. `UBERON:0123456`). It matches the prefix shape but is **not** checked
against the live ontology. If your validation materializes the ontology, supply
real terms via a hint (`choices: [...]`).

### Counts are clamped

`--count-for X=N` is clamped to `[1, 1000]`. You can't drop a collection to zero
with counts — use [`--exclude`](scope.md) instead. Raise the ceiling via the
Python API (`GenerationConfig(max_count=...)`).

## Troubleshooting

### `--validate` reports errors

Run with `--validate` and read the messages on stderr. Common causes:

- **A schema constraint the generator doesn't enforce** (a rule, expression, or
  `unique_key`). See above — these are documented gaps.
- **An empty/stub enum** (no permissible values and no `reachable_from`). The
  generator emits a placeholder token, which only validates if the schema accepts
  free strings there. Add permissible values, or pin a value with a hint.
- **A very restrictive `pattern`** that `rstr` can't satisfy cleanly. Provide an
  explicit `choices`/`const` hint for that slot.

### `FileNotFoundError` for an imported module during validation

LinkML resolves relative imports from the **schema's own directory**. The CLI's
`--validate` handles this automatically. If you validate yourself, `chdir` to the
schema's directory first (see [Python API → Validating](python-api.md#validating-programmatically)).

### Module-based `--select` selects nothing / everything

Module matching uses each class's `from_schema`. If you pre-merged the schema
into a single file, all classes report the same module and module selection
collapses. Pass the **unmerged** multi-file schema (the generator loads it
unmerged by default).

### Output isn't reproducible across runs

Set an explicit `--seed` (the default is `0`; `-1` means nondeterministic). The
generator is otherwise fully deterministic — it isolates Faker's RNG and uses a
fixed date window, so wall-clock time doesn't leak in. If you still see drift,
check that you're not passing `seed=None`/`--seed -1`.

### Install fails building a dependency wheel

Some systems ship a patched `pip`/`setuptools` that fails on certain LinkML
deps. Use a fresh virtual environment:

```bash
python -m venv .venv && .venv/bin/pip install -e .
```

### Generation is slow / output is huge

Output size scales with counts. Lower `-n`, scope to fewer collections with
`--select`, or lower `--optional-prob`. Validation of very large documents
(tens of thousands of objects) is the slower step, not generation.
