"""End-to-end tests: generated data must validate against its schema."""

from __future__ import annotations

import contextlib
import datetime
import os
import re
from pathlib import Path

import pytest
from linkml.validator import validate

from linkml_data_gen import DataGenerator, GenerationConfig

HERE = Path(__file__).parent
EDGE = HERE / "schemas" / "edge.yaml"
# The real-world bootstrap schema, used when present as a sibling checkout
# (HERE = .../linkml-data-gen/tests ; parents[1] = the directory holding both repos).
BRAINBANK = HERE.parents[1] / "brainbank-hippo-schema" / "schema" / "brainbank.yaml"

SEEDS = [0, 1, 2, 3, 7, 42, 99]


@contextlib.contextmanager
def _in_dir(path):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _assert_valid(instance, schema_path, target_class):
    schema_path = Path(schema_path)
    # Resolve relative imports from the schema's own directory.
    with _in_dir(schema_path.parent):
        report = validate(instance, schema_path.name, target_class)
    assert not report.results, "\n".join(
        f"{r.severity} {r.message}" for r in report.results[:20]
    )


# --------------------------------------------------------------------- edge
@pytest.mark.parametrize("seed", SEEDS)
def test_edge_schema_validates(seed):
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=seed, default_count=5))
    data = gen.generate()
    _assert_valid(data, EDGE, "Registry")


def test_determinism():
    a = DataGenerator(str(EDGE), GenerationConfig(seed=123)).generate()
    b = DataGenerator(str(EDGE), GenerationConfig(seed=123)).generate()
    assert a == b


def test_different_seeds_differ():
    a = DataGenerator(str(EDGE), GenerationConfig(seed=1)).generate()
    b = DataGenerator(str(EDGE), GenerationConfig(seed=2)).generate()
    assert a != b


def test_required_slots_always_present():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=5, default_count=10))
    data = gen.generate()
    for w in data["widgets"]:
        for req in ("widget_id", "serial", "weight_g", "status", "tags"):
            assert req in w, f"missing required slot {req}"


def test_identifier_pattern_respected():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=7, default_count=8))
    data = gen.generate()
    for w in data["widgets"]:
        assert re.match(r"^WIDGET:[0-9]{4}$", w["widget_id"])
        assert re.match(r"^[A-Z]{3}-[0-9]{2,4}[a-z]$", w["serial"])


def test_numeric_bounds_respected():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=3, default_count=20))
    data = gen.generate()
    for w in data["widgets"]:
        assert 0.5 <= w["weight_g"] <= 9.9
        if "ports" in w:
            assert 1 <= w["ports"] <= 8


def test_references_resolve_to_existing_entities():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=2, default_count=8))
    data = gen.generate()
    team_ids = {t["team_id"] for t in data["teams"]}
    for w in data["widgets"]:
        if "owner" in w:
            assert w["owner"] in team_ids, "dangling reference in container mode"


def test_no_empty_inline_objects():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=4, default_count=10))
    data = gen.generate()
    for w in data["widgets"]:
        for spec in w.get("specs", []):
            assert spec, "empty inline object emitted"


def test_unique_identifiers():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=9, default_count=30))
    data = gen.generate()
    ids = [w["widget_id"] for w in data["widgets"]]
    assert len(ids) == len(set(ids)), "duplicate identifiers"


# Sibling classes whose names share a capital-letter signature abbreviate to
# the same id prefix (here both "AB"). Ids must still be globally unique — a
# consumer with one id namespace (e.g. a store with a shared entity registry)
# rejects the dataset otherwise. Regression for the pattern-less mint path,
# which previously trusted per-class counters and collided across classes.
_COLLIDING_ABBREV_SCHEMA = """
id: https://example.org/collide
name: collide
prefixes:
  linkml: https://w3id.org/linkml/
default_prefix: collide
default_range: string
imports:
  - linkml:types
classes:
  Container:
    tree_root: true
    attributes:
      alpha_betas:
        range: AlphaBeta
        multivalued: true
        inlined_as_list: true
      alpha_bravos:
        range: AlphaBravo
        multivalued: true
        inlined_as_list: true
  AlphaBeta:
    attributes:
      id:
        identifier: true
      name: {}
  AlphaBravo:
    attributes:
      id:
        identifier: true
      name: {}
"""


def test_identifiers_unique_across_classes_with_shared_abbrev(tmp_path):
    schema = tmp_path / "collide.yaml"
    schema.write_text(_COLLIDING_ABBREV_SCHEMA)
    data = DataGenerator(
        str(schema), GenerationConfig(seed=0, default_count=25)
    ).generate()
    ids = [e["id"] for e in data["alpha_betas"]] + [
        e["id"] for e in data["alpha_bravos"]
    ]
    assert len(ids) == len(set(ids)), "id collision across classes sharing an abbrev"


def test_count_overrides():
    cfg = GenerationConfig(seed=0, count_overrides={"widgets": 12, "teams": 3})
    data = DataGenerator(str(EDGE), cfg).generate()
    assert len(data["widgets"]) == 12
    assert len(data["teams"]) == 3


def test_datetime_is_timezone_aware():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=1, default_count=10))
    data = gen.generate()
    seen = False
    for w in data["widgets"]:
        if "created_on" in w:
            seen = True
            datetime.datetime.fromisoformat(w["created_on"])  # parses
            assert ("+" in w["created_on"]) or w["created_on"].endswith("Z")
    assert seen


def test_single_class_list_mode():
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=0))
    items = gen.generate_list("Team", count=4)
    assert len(items) == 4
    assert all("team_id" in t and "email" in t for t in items)


def test_explicit_root_class():
    # Generating with an explicit non-tree-root container-less class yields a
    # single self-contained instance.
    gen = DataGenerator(str(EDGE), GenerationConfig(seed=0))
    inst = gen.generate(root_class="Team")
    assert "team_id" in inst and "email" in inst


# ---------------------------------------------------------------- brainbank
brainbank_available = BRAINBANK.exists()
needs_bb = pytest.mark.skipif(not brainbank_available, reason="brainbank schema not present")


@needs_bb
@pytest.mark.parametrize("seed", SEEDS)
def test_brainbank_validates(seed):
    gen = DataGenerator(str(BRAINBANK), GenerationConfig(seed=seed, default_count=6))
    data = gen.generate()
    _assert_valid(data, BRAINBANK, "BrainBank")


@needs_bb
def test_brainbank_scales():
    cfg = GenerationConfig(seed=1, default_count=10,
                           count_overrides={"donors": 50, "samples": 200})
    gen = DataGenerator(str(BRAINBANK), cfg)
    data = gen.generate()
    assert len(data["donors"]) == 50
    assert len(data["samples"]) >= 200  # may grow via on-demand references
    _assert_valid(data, BRAINBANK, "BrainBank")


@needs_bb
def test_brainbank_polymorphism():
    """The abstract `samples` collection should hold varied concrete subtypes."""
    gen = DataGenerator(str(BRAINBANK), GenerationConfig(seed=3, default_count=30))
    data = gen.generate()
    categories = {s.get("category") for s in data["samples"]}
    assert len(categories) > 3, f"expected polymorphic variety, got {categories}"
