# Contributing to linkml-data-gen

Thanks for your interest in improving linkml-data-gen! This project generates
realistic, schema-valid test data from any LinkML schema. Contributions of all
kinds are welcome — bug reports, feature ideas, documentation, and code.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** or **request a feature** via the
  [issue templates](.github/ISSUE_TEMPLATE).
- **Improve the docs** in [`docs/`](docs/index.md) or this file.
- **Fix a bug / add a feature** with a pull request (see below).

A great bug report includes a **minimal LinkML schema** that reproduces the
problem, the exact command (or Python snippet) you ran, what you expected, and
what you got. The schema is the most important part — it lets us reproduce
immediately.

## Development setup

Python ≥ 3.9. Use a virtual environment:

```bash
git clone https://github.com/BU-Neuromics/linkml-data-gen
cd linkml-data-gen
python -m venv .venv
.venv/bin/pip install -e ".[test]"
```

Verify your setup:

```bash
.venv/bin/python -m pytest -q
```

## Running the tests

```bash
.venv/bin/python -m pytest            # whole suite
.venv/bin/python -m pytest -k hint    # a subset
```

The suite validates generated data against:

- a synthetic edge-case schema (`tests/schemas/edge.yaml`) — patterns, bounds,
  mixins, inlined value objects, references;
- a two-module schema (`tests/schemas/inventory.yaml` + `people.yaml`) — for
  module-based scope selection;
- the real `brainbank-hippo-schema`, **if** it's checked out as a sibling
  directory (those tests skip automatically when it isn't).

If your change affects generation, please add or update tests so the new
behavior is validated against a schema, not just asserted in the abstract. New
LinkML features are best covered by adding a small class/slot to
`tests/schemas/edge.yaml` and asserting the result both validates and has the
expected shape.

### A note on determinism

Generation must stay reproducible: identical `(schema, seed, config)` must
produce byte-identical output. When adding randomness, draw it from the seeded
RNG (`self.fake`, `self.fake.random`, or the seeded `rstr` instance) — never the
global `random`/`Faker.seed()` or wall-clock time. There is a determinism test;
please keep it green.

## Coding guidelines

- Match the surrounding style: type hints, short focused methods, and comments
  that explain *why* (not *what*).
- Keep generation **schema-driven** — derive behavior from `SchemaView`, don't
  hard-code assumptions about a particular schema.
- Prefer producing **valid** output by construction; if a LinkML feature can't be
  honored yet, document it under "what isn't enforced" rather than emitting
  invalid data.
- No new hard dependencies without discussion.

See [`docs/how-it-works.md`](docs/how-it-works.md) for the architecture and the
module map before making larger changes.

## Pull request process

1. Fork and create a branch from `main`.
2. Make your change with tests and docs.
3. Run `pytest` locally; ensure it passes.
4. Open a PR using the template. Describe the change, link any issue, and note
   whether output format/behavior changed.
5. CI runs the test suite on supported Python versions. A maintainer will review.

Small, focused PRs are easier to review and land faster. If you're planning a
large change, open an issue first to discuss the approach.

## Releasing (maintainers)

1. Update [`CHANGELOG.md`](CHANGELOG.md) (move items from *Unreleased* into a new
   version section).
2. Bump the version in `pyproject.toml` and `src/linkml_data_gen/__init__.py`.
3. Tag the release (`vX.Y.Z`) and push the tag.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
