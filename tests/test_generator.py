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


# -------------------------------------------------------------------- hints
from linkml_data_gen.hints import FieldHint, HintRegistry  # noqa: E402

EDGE_HINTS = {
    "slots": {
        "weight_g": {"distribution": "normal", "params": {"mean": 5, "std": 1},
                     "minimum": 0.5, "maximum": 9.9},
        "ports": {"choices": [1, 2, 4]},
        "status": {"choices": ["active"]},
        "created_by": {"const": "system", "prob": 1.0},
        "created_on": {"date_start": "2020-01-01", "date_end": "2020-12-31", "prob": 1.0},
    },
    "classes": {
        "Widget": {
            "tags": {"cardinality": {"min": 2, "max": 2, "dist": "fixed"}},
            "owner": {"prob": 0.0},
        }
    },
}


def _hinted(seed=0, count=15):
    cfg = GenerationConfig(seed=seed, default_count=count, hints=EDGE_HINTS)
    return DataGenerator(str(EDGE), cfg).generate()


def test_hints_preserve_validity():
    _assert_valid(_hinted(), EDGE, "Registry")


def test_hint_const_and_choices_and_enum():
    data = _hinted(seed=1)
    for w in data["widgets"]:
        assert w["status"] == "active"               # enum choices
        if "ports" in w:
            assert w["ports"] in (1, 2, 4)            # scalar choices
        if "created_by" in w:
            assert w["created_by"] == "system"        # const
        assert w["created_on"].startswith("2020")     # date window


def test_hint_distribution_bounds_and_mean():
    data = _hinted(seed=2, count=60)
    weights = [w["weight_g"] for w in data["widgets"]]
    assert all(0.5 <= x <= 9.9 for x in weights)
    assert 4.0 <= (sum(weights) / len(weights)) <= 6.0  # ~Normal(5,1)


def test_hint_cardinality_fixed():
    data = _hinted(seed=3)
    assert all(len(w["tags"]) == 2 for w in data["widgets"])


def test_hint_population_probability_zero():
    data = _hinted(seed=4, count=20)
    assert all("owner" not in w for w in data["widgets"])


def test_hints_are_deterministic():
    assert _hinted(seed=7) == _hinted(seed=7)


def test_hint_registry_precedence():
    reg = HintRegistry({
        "types": {"float": {"minimum": 0, "maximum": 1}},
        "slots": {"weight_g": {"minimum": 5}},
        "classes": {"Widget": {"weight_g": {"maximum": 50}}},
    })
    h = reg.for_slot("Widget", "weight_g", "float")
    assert h.minimum == 5     # slot overrides type
    assert h.maximum == 50    # class.slot overrides type
    # A slot with only the type-level hint still sees it.
    h2 = reg.for_slot("Other", "misc", "float")
    assert h2.minimum == 0 and h2.maximum == 1


def test_field_hint_dict_choices_to_weights():
    h = FieldHint.from_dict({"choices": {"a": 3, "b": 1}})
    assert h.choices == ["a", "b"]
    assert h.weights == [3, 1]


def test_poisson_cardinality_within_bounds():
    cfg = GenerationConfig(seed=5, default_count=40, hints={
        "classes": {"Widget": {"tags": {"cardinality": {"min": 1, "max": 6,
                                                         "dist": "poisson", "lam": 2}}}}})
    data = DataGenerator(str(EDGE), cfg).generate()
    assert all(1 <= len(w["tags"]) <= 6 for w in data["widgets"])


# -------------------------------------------------------------------- scope
INVENTORY = HERE / "schemas" / "inventory.yaml"


def _inv(**kw):
    return DataGenerator(str(INVENTORY), GenerationConfig(seed=0, default_count=4, **kw)).generate()


def test_scope_select_module_strict():
    data = _inv(select=["inventory"])
    assert set(data) == {"products"}                 # only the inventory module
    # cross-module reference is a dangling-but-valid id (no Employee pulled in)
    assert isinstance(data["products"][0]["managed_by"], str)
    _assert_valid(data, INVENTORY, "Warehouse")


def test_scope_select_with_dependencies():
    data = _inv(select=["inventory"], with_dependencies=True)
    assert "products" in data and "staff" in data     # Employee pulled in
    emp_ids = {e["employee_id"] for e in data["staff"]}
    assert data["products"][0]["managed_by"] in emp_ids  # resolves to a real one
    _assert_valid(data, INVENTORY, "Warehouse")


def test_scope_select_other_module():
    data = _inv(select=["people"])
    assert set(data) == {"staff"}                     # products excluded
    _assert_valid(data, INVENTORY, "Warehouse")


def test_scope_exclude_collection_name():
    data = _inv(exclude=["staff"])
    assert "staff" not in data and "products" in data


def test_scope_default_includes_everything():
    data = _inv()
    assert {"products", "staff"} <= set(data)


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
def test_brainbank_with_hints_validates():
    hints = {
        "slots": {"sex": {"choices": {"male": 55, "female": 45}}},
        "classes": {"Donor": {"age_at_death": {"distribution": "normal",
                                               "params": {"mean": 68, "std": 12},
                                               "minimum": 21, "maximum": 102}}},
    }
    cfg = GenerationConfig(seed=2, default_count=6, hints=hints)
    data = DataGenerator(str(BRAINBANK), cfg).generate()
    for dn in data["donors"]:
        if "age_at_death" in dn:
            assert 21 <= dn["age_at_death"] <= 102
        if "sex" in dn:
            assert dn["sex"] in ("male", "female")
    _assert_valid(data, BRAINBANK, "BrainBank")


@needs_bb
def test_brainbank_tissue_scope():
    cfg = GenerationConfig(seed=0, default_count=5, select=["tissue"])
    data = DataGenerator(str(BRAINBANK), cfg).generate()
    assert set(data) <= {"samples", "processes", "containers", "locations"}
    assert "donors" not in data and "datasets" not in data
    # only tissue-module concrete subtypes fill the polymorphic `samples`
    assert {s["category"] for s in data["samples"]} <= {"SolidSample", "LiquidSample"}
    _assert_valid(data, BRAINBANK, "BrainBank")


@needs_bb
def test_brainbank_polymorphism():
    """The abstract `samples` collection should hold varied concrete subtypes."""
    gen = DataGenerator(str(BRAINBANK), GenerationConfig(seed=3, default_count=30))
    data = gen.generate()
    categories = {s.get("category") for s in data["samples"]}
    assert len(categories) > 3, f"expected polymorphic variety, got {categories}"
