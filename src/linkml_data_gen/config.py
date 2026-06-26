"""Configuration for stochastic LinkML data generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GenerationConfig:
    """Knobs controlling how much data is generated and how it varies.

    All randomness flows from ``seed`` so a run is fully reproducible. Counts can
    be tuned globally (``default_count``) or per collection/class
    (``count_overrides``), which lets the same generator scale from a tiny smoke
    test to a large fixture without code changes.
    """

    # Reproducibility. None -> nondeterministic.
    seed: Optional[int] = 0

    # How many instances to put in each top-level (tree_root) collection by
    # default, and how to clamp it.
    default_count: int = 5
    min_count: int = 1
    max_count: int = 1000

    # Per-collection / per-class overrides, keyed by either the root slot name
    # (e.g. "donors") or a class name (e.g. "Donor"). Slot name wins.
    count_overrides: dict[str, int] = field(default_factory=dict)

    # Probability that a non-required slot is populated. ``recommended`` slots
    # use the higher probability; everything else optional uses the lower one.
    recommended_prob: float = 0.95
    optional_prob: float = 0.55

    # Default cardinality window for multivalued slots without explicit
    # minimum_cardinality / maximum_cardinality.
    multivalued_min: int = 1
    multivalued_max: int = 4

    # Maximum recursion depth when *inlining* nested objects (guards against
    # self-referential inlined ranges). Reference slots never recurse.
    max_depth: int = 6

    # Faker locale.
    locale: str = "en_US"

    # Domain / sampling hints. Either a parsed hints document (dict with
    # ``types`` / ``slots`` / ``classes`` keys) or a HintRegistry. See
    # ``linkml_data_gen.hints`` for the format.
    hints: Any = None

    # Scope control. Tokens match a collection's slot name, its range class
    # name, or that class's source module (e.g. "tissue"). ``select`` keeps only
    # matching collections/classes (None = everything); ``exclude`` drops
    # matching ones. Scope also restricts which concrete subtypes fill a
    # polymorphic collection.
    select: Optional[list] = None
    exclude: Optional[list] = None

    # When True, collections needed to satisfy references from in-scope data are
    # generated too (self-contained output). When False (default), references to
    # out-of-scope classes become valid-but-dangling id strings.
    with_dependencies: bool = False

    def count_for(self, slot_name: str, class_name: Optional[str] = None) -> int:
        """Resolve the instance count for a collection, honouring overrides."""
        if slot_name in self.count_overrides:
            n = self.count_overrides[slot_name]
        elif class_name and class_name in self.count_overrides:
            n = self.count_overrides[class_name]
        else:
            n = self.default_count
        return max(self.min_count, min(self.max_count, n))
