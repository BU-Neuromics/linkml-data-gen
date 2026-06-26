"""Domain hints and sampling-distribution configuration.

A *hint* overrides how a particular slot's value is generated, letting callers
inject domain knowledge the schema doesn't carry: a realistic distribution
(``age ~ Normal(75, 12)``), a weighted categorical (``sex`` 48/48/4), a fixed
choice list, a Faker provider, a constant, a regex, a date window, a population
probability, or a cardinality distribution.

Hints are declarative data (a dict, or a YAML/JSON file); :class:`HintRegistry`
resolves the most specific hint for a given ``(class, slot, range)`` and the
:class:`~linkml_data_gen.values.ValueFactory` applies it. Sampling uses the
generator's seeded RNG, so hinted runs remain fully reproducible.

Example document::

    types:
      float: {distribution: uniform}          # default for all floats
    slots:
      sex: {choices: [male, female, unknown], weights: [48, 48, 4]}
      age_at_death: {distribution: normal, params: {mean: 75, std: 12},
                     minimum: 18, maximum: 100, integer: true}
    classes:
      Donor:
        post_mortem_interval_hours:
          {distribution: lognormal, params: {mean: 2.5, sigma: 0.6}, maximum: 120}
        cohort: {cardinality: {min: 1, max: 3, dist: poisson, lam: 1.5}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

_UNSET = object()


@dataclass
class FieldHint:
    """Resolved instructions for generating one slot's value(s)."""

    # Value-shaping (checked in this order).
    const: Any = _UNSET
    choices: Optional[list] = None
    weights: Optional[list] = None
    faker: Optional[str] = None
    faker_args: Optional[list] = None
    faker_kwargs: Optional[dict] = None
    pattern: Optional[str] = None

    # Numeric distribution. ``distribution`` in
    # {uniform, normal/gaussian, lognormal, exponential, int/int_uniform}.
    distribution: Optional[str] = None
    params: dict = field(default_factory=dict)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    integer: Optional[bool] = None

    # Date/datetime window (ISO strings or Faker-style "-10y"/"today").
    date_start: Optional[str] = None
    date_end: Optional[str] = None

    # Slot-level behaviour.
    prob: Optional[float] = None  # population probability override
    cardinality_min: Optional[int] = None
    cardinality_max: Optional[int] = None
    cardinality_dist: Optional[str] = None  # uniform | fixed | poisson
    cardinality_lam: Optional[float] = None

    @property
    def has_const(self) -> bool:
        return self.const is not _UNSET

    @property
    def is_empty(self) -> bool:
        return (
            not self.has_const
            and self.choices is None
            and self.faker is None
            and self.pattern is None
            and self.distribution is None
            and self.date_start is None
            and self.date_end is None
            and self.prob is None
            and self.minimum is None
            and self.maximum is None
            and self.cardinality_min is None
            and self.cardinality_max is None
            and self.cardinality_dist is None
        )

    @classmethod
    def from_dict(cls, d: dict) -> "FieldHint":
        d = dict(d or {})
        card = d.pop("cardinality", None) or {}
        # Normalise a dict-style {value: weight} choices form.
        choices = d.get("choices")
        weights = d.get("weights")
        if isinstance(choices, dict):
            weights = list(choices.values())
            choices = list(choices.keys())
        return cls(
            const=d.get("const", _UNSET),
            choices=choices,
            weights=weights,
            faker=d.get("faker"),
            faker_args=d.get("faker_args"),
            faker_kwargs=d.get("faker_kwargs"),
            pattern=d.get("pattern"),
            distribution=d.get("distribution") or d.get("dist"),
            params=d.get("params", {}) or {},
            minimum=d.get("minimum", d.get("min")),
            maximum=d.get("maximum", d.get("max")),
            integer=d.get("integer"),
            date_start=d.get("date_start"),
            date_end=d.get("date_end"),
            prob=d.get("prob"),
            cardinality_min=card.get("min"),
            cardinality_max=card.get("max"),
            cardinality_dist=card.get("dist"),
            cardinality_lam=card.get("lam"),
        )


class HintRegistry:
    """Holds hint dicts by selector and resolves the most specific one.

    Precedence (low → high): ``types[range]`` < ``slots[slot]`` <
    ``classes[Class][slot]``. More specific selectors override individual keys
    of less specific ones.
    """

    def __init__(self, document: Optional[Union[dict, "HintRegistry"]] = None):
        self._types: dict[str, dict] = {}
        self._slots: dict[str, dict] = {}
        self._classes: dict[str, dict[str, dict]] = {}
        self._cache: dict[tuple, FieldHint] = {}
        if isinstance(document, HintRegistry):
            self._types = dict(document._types)
            self._slots = dict(document._slots)
            self._classes = {k: dict(v) for k, v in document._classes.items()}
        elif document:
            self._load(document)

    def _load(self, doc: dict) -> None:
        self._types.update(doc.get("types", {}) or {})
        self._slots.update(doc.get("slots", {}) or {})
        for cls, slots in (doc.get("classes", {}) or {}).items():
            self._classes.setdefault(cls, {}).update(slots or {})
        # Convenience: flat "Class.slot" keys at top level.
        for key, val in doc.items():
            if key in ("types", "slots", "classes"):
                continue
            if "." in key:
                cls, slot = key.split(".", 1)
                self._classes.setdefault(cls, {})[slot] = val
            else:
                self._slots.setdefault(key, val)

    @property
    def empty(self) -> bool:
        return not (self._types or self._slots or self._classes)

    def for_slot(
        self, class_name: Optional[str], slot_name: str, range_name: Optional[str]
    ) -> FieldHint:
        key = (class_name, slot_name, range_name)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        merged: dict = {}
        if range_name and range_name in self._types:
            merged.update(self._types[range_name])
        if slot_name in self._slots:
            merged.update(self._slots[slot_name])
        if class_name and class_name in self._classes:
            cls_slots = self._classes[class_name]
            if slot_name in cls_slots:
                merged.update(cls_slots[slot_name])
        hint = FieldHint.from_dict(merged)
        self._cache[key] = hint
        return hint
