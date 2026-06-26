"""Generate stochastic, schema-valid instance data from any LinkML schema.

The generator is driven entirely by :class:`~linkml_runtime.SchemaView`, so it
inherits LinkML's own resolution of imports, inheritance, ``slot_usage`` and
inlining rules. It supports two modes:

* **Container mode** (the common case): the schema has a ``tree_root`` class
  whose multivalued, inlined slots are collections. Instances are pooled and
  cross-referenced by identifier, producing a connected, referentially-consistent
  graph — the same shape as a hand-written fixture.

* **Single-class mode**: generate one instance (or a list) of an arbitrary
  class, inlining nested objects and emitting plausible identifier strings for
  reference slots.

The design favours correctness on real schemas: two-phase generation (allocate
all pooled shells, then fill them) guarantees every reference resolves, even
across cyclic dependencies between collections.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from faker import Faker
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition

from .config import GenerationConfig
from .values import ValueFactory


class DataGenerator:
    def __init__(
        self,
        schema: Union[str, SchemaView],
        config: Optional[GenerationConfig] = None,
    ):
        self.sv = schema if isinstance(schema, SchemaView) else SchemaView(schema)
        self.config = config or GenerationConfig()
        self.fake = Faker(self.config.locale)
        if self.config.seed is not None:
            # seed_instance isolates this instance's RNG; we deliberately avoid
            # the Faker.seed() classmethod, which mutates global shared state.
            self.fake.seed_instance(self.config.seed)
        self.values = ValueFactory(self.fake, seed=self.config.seed)
        self._descendant_cache: dict[str, tuple[str, ...]] = {}

        # Per-run mutable state (reset in _reset_state).
        self._pool: dict[str, list[str]] = {}
        self._collections: dict[str, list[dict]] = {}
        self._pending: list[tuple[dict, str]] = []
        self._container_mode = False
        self._home_slot: dict[str, Optional[str]] = {}

    # ------------------------------------------------------------------ public
    @property
    def tree_root(self) -> Optional[str]:
        for name, c in self.sv.all_classes().items():
            if c.tree_root:
                return name
        return None

    def generate(self, root_class: Optional[str] = None) -> Any:
        """Generate the root object for the schema.

        With a ``tree_root`` (or a class that has collection slots) this returns
        a populated container dict. Otherwise it returns a single instance.
        """
        rc = root_class or self.tree_root
        if rc is None:
            raise ValueError(
                "Schema has no tree_root; pass root_class=... or use generate_list()."
            )
        if rc not in self.sv.all_classes():
            raise ValueError(f"Unknown class: {rc}")
        self._reset_state()
        if self._collection_slots(rc):
            return self._generate_container(rc)
        return self._build_instance(rc, depth=0)

    def generate_list(self, class_name: str, count: Optional[int] = None) -> list:
        """Generate a list of independent instances of ``class_name``."""
        if class_name not in self.sv.all_classes():
            raise ValueError(f"Unknown class: {class_name}")
        self._reset_state()
        n = count if count is not None else self.config.default_count
        return [self._build_instance(class_name, depth=0) for _ in range(n)]

    # ------------------------------------------------------------- container
    def _reset_state(self) -> None:
        self._pool = {}
        self._collections = {}
        self._pending = []
        self._container_mode = False
        self._home_slot = {}
        self._used_ids = set()
        self.values._id_counters = {}

    def _generate_container(self, rc: str) -> dict:
        self._container_mode = True
        root: dict[str, Any] = {}
        coll_slots = self._collection_slots(rc)

        # Map every concrete class to the most specific collection that can host
        # it, so on-demand reference targets land somewhere they will serialize.
        self._build_home_map(coll_slots)

        for slot in coll_slots:
            self._collections[slot.name] = []
            root[slot.name] = self._collections[slot.name]

        # Phase A: allocate shells (id + type designator) for every collection
        # *before* filling any, so references can resolve in any order.
        for slot in coll_slots:
            n = self.config.count_for(slot.name, slot.range)
            for _ in range(n):
                cls = self._choose_concrete(slot.range)
                self._allocate(cls, home_slot=slot.name)

        # Non-collection scalar/reference slots that live directly on the root.
        for slot in self.sv.class_induced_slots(rc):
            if slot.name in self._collections or self._is_identifier(slot):
                continue
            if self._is_designates_type(slot):
                root[slot.name] = rc
                continue
            if self._should_populate(slot):
                val = self._gen_slot_value(slot, depth=0)
                if val not in (None, []):
                    root[slot.name] = val

        # Phase B: fill all pooled shells (queue absorbs on-demand additions).
        while self._pending:
            shell, cls = self._pending.pop(0)
            self._populate_slots(shell, cls, depth=0)

        # Drop collections that ended up empty for cleaner output.
        return {k: v for k, v in root.items() if v not in (None, [], {})}

    # --------------------------------------------------------------- building
    def _allocate(self, cls: str, home_slot: Optional[str]) -> tuple[dict, Optional[str]]:
        """Create a shell (id + designator) and queue it for filling."""
        shell, _id = self._make_shell(cls)
        if home_slot is not None:
            self._collections.setdefault(home_slot, []).append(shell)
        self._pending.append((shell, cls))
        return shell, _id

    def _make_shell(self, cls: str) -> tuple[dict, Optional[str]]:
        shell: dict[str, Any] = {}
        _id = None
        ident = self.sv.get_identifier_slot(cls)
        if ident is not None:
            _id = self._mint_identifier(cls, ident)
            shell[ident.name] = _id
            self._pool.setdefault(cls, []).append(_id)
        dt = self._designates_slot(cls)
        if dt is not None:
            shell[dt.name] = cls
        return shell, _id

    def _mint_identifier(self, cls: str, ident: SlotDefinition) -> str:
        """Mint a unique identifier, honouring a ``pattern`` on the id slot."""
        if ident.pattern:
            for _ in range(50):
                v = self.values._from_pattern(ident.pattern)
                if v not in self._used_ids:
                    break
            else:
                v = f"{v}{len(self._used_ids)}"
        else:
            v = self.values.mint_id(cls)
        self._used_ids.add(v)
        return v

    def _build_instance(self, cls: str, depth: int, ensure_nonempty: bool = False) -> dict:
        """Build a fully-populated instance now (used for inline / single mode)."""
        shell, ident = self._make_shell(cls)
        self._populate_slots(shell, cls, depth)
        if ensure_nonempty and not shell:
            self._force_one_leaf(shell, cls, depth)
        return shell

    def _force_one_leaf(self, shell: dict, cls: str, depth: int) -> None:
        """Populate a single leaf slot so a value object is never bare ``{}``."""
        for slot in self.sv.class_induced_slots(cls):
            rng = slot.range or "string"
            if rng in self.sv.all_classes():
                continue
            val = self._gen_slot_value(slot, depth)
            if val not in (None, []):
                shell[slot.name] = val
                return

    def _populate_slots(self, shell: dict, cls: str, depth: int) -> None:
        for slot in self.sv.class_induced_slots(cls):
            if slot.name in shell:  # identifier / designator already set
                continue
            if self._is_designates_type(slot):
                shell[slot.name] = cls
                continue
            if self._is_identifier(slot):
                _id = self._mint_identifier(cls, slot)
                shell[slot.name] = _id
                self._pool.setdefault(cls, []).append(_id)
                continue
            if not self._should_populate(slot):
                continue
            val = self._gen_slot_value(slot, depth)
            if val not in (None, []):
                shell[slot.name] = val

    # ---------------------------------------------------------------- values
    def _gen_slot_value(self, slot: SlotDefinition, depth: int) -> Any:
        if slot.multivalued:
            lo, hi = self._cardinality(slot)
            # Reference slots should not repeat the same identifier; inlined
            # objects are independent and may "repeat" structurally.
            dedupe = (
                slot.range in self.sv.all_classes() and not self.sv.is_inlined(slot)
            )
            items: list = []
            for _ in range(self.fake.random_int(lo, hi)):
                v = self._gen_single(slot, depth)
                if v is None:
                    continue
                if dedupe and v in items:
                    continue
                items.append(v)
            return items
        return self._gen_single(slot, depth)

    def _gen_single(self, slot: SlotDefinition, depth: int) -> Any:
        rng = slot.range or self.sv.schema.default_range or "string"
        if rng in self.sv.all_enums():
            return self.values.enum_value(self.sv.get_enum(rng))
        if rng in self.sv.all_classes():
            return self._gen_class_value(slot, rng, depth)
        # A (possibly derived) type: resolve to its base for generation.
        tdef = self.sv.get_type(rng) if rng in self.sv.all_types() else None
        return self.values.scalar(slot, tdef)

    def _gen_class_value(self, slot: SlotDefinition, rng: str, depth: int) -> Any:
        if self.sv.is_inlined(slot):
            concrete = self._choose_concrete(rng)
            if depth >= self.config.max_depth:
                obj = self._minimal_inline(concrete)
            else:
                obj = self._build_instance(concrete, depth + 1, ensure_nonempty=True)
            # Avoid emitting bare {} for all-optional value objects.
            return obj if obj else None
        return self._reference_to(rng, depth)

    def _minimal_inline(self, cls: str) -> dict:
        """Depth-capped inline: only required leaf (scalar/enum) slots."""
        shell, _ = self._make_shell(cls)
        for slot in self.sv.class_induced_slots(cls):
            if slot.name in shell or not slot.required:
                continue
            rng = slot.range or "string"
            if rng in self.sv.all_classes():
                continue  # stop the recursion here
            shell[slot.name] = self._gen_slot_value(slot, self.config.max_depth)
        return shell

    def _reference_to(self, rng: str, depth: int) -> Any:
        """Return an identifier for an instance of ``rng`` (or a descendant)."""
        candidates = [
            c for c in self._concrete_descendants(rng) if self.sv.get_identifier_slot(c)
        ]
        pool_ids = [i for c in candidates for i in self._pool.get(c, [])]

        if not self._container_mode:
            # No container to host real targets: emit a valid, if dangling, id.
            cls = self._choose_concrete(rng)
            return self.values.mint_id(cls)

        # Reuse an existing instance whenever the pool can satisfy the range.
        # This keeps collection sizes predictable: a collection only grows past
        # its configured count when a specific subtype is demanded but was never
        # pre-allocated (pool empty), in which case we must create one.
        if pool_ids:
            return self.fake.random_element(pool_ids)

        cls = self._choose_concrete_with_home(rng)
        home = self._home_slot.get(cls)
        if home is None:
            if pool_ids:
                return self.fake.random_element(pool_ids)
            # Nowhere to put it and nothing to point at: inline a minimal object.
            return self._minimal_inline(self._choose_concrete(rng))
        _, _id = self._allocate(cls, home_slot=home)
        return _id if _id is not None else self.fake.random_element(pool_ids or [self.values.mint_id(cls)])

    # ----------------------------------------------------------- class choice
    def _choose_concrete(self, rng: str) -> str:
        concretes = self._concrete_descendants(rng)
        if not concretes:
            return rng  # abstract with no concrete impl; best effort
        return self.fake.random_element(concretes)

    def _choose_concrete_with_home(self, rng: str) -> str:
        concretes = self._concrete_descendants(rng)
        homed = [c for c in concretes if self._home_slot.get(c) is not None]
        pool = homed or concretes or [rng]
        return self.fake.random_element(pool)

    def _concrete_descendants(self, rng: str) -> tuple[str, ...]:
        cached = self._descendant_cache.get(rng)
        if cached is not None:
            return cached
        if rng not in self.sv.all_classes():
            self._descendant_cache[rng] = ()
            return ()
        out = []
        for c in self.sv.class_descendants(rng, reflexive=True):
            cd = self.sv.get_class(c)
            if not cd.abstract and not cd.mixin:
                out.append(c)
        result = tuple(out)
        self._descendant_cache[rng] = result
        return result

    def _build_home_map(self, coll_slots: list[SlotDefinition]) -> None:
        """For each concrete class, choose the most specific hosting collection."""
        self._home_slot = {}
        for cname, c in self.sv.all_classes().items():
            if c.abstract or c.mixin:
                continue
            best_slot, best_depth = None, -1
            for slot in coll_slots:
                rng = slot.range
                if rng in self.sv.all_classes() and cname in self._concrete_descendants(rng):
                    # Prefer the collection whose range is most specific (the
                    # deepest range class still has cname as a descendant).
                    depth = len(self.sv.class_ancestors(rng))
                    if depth > best_depth:
                        best_depth, best_slot = depth, slot.name
            self._home_slot[cname] = best_slot

    # -------------------------------------------------------------- predicates
    def _collection_slots(self, cls: str) -> list[SlotDefinition]:
        out = []
        for slot in self.sv.class_induced_slots(cls):
            rng = slot.range
            if slot.multivalued and rng in self.sv.all_classes() and self.sv.is_inlined(slot):
                out.append(slot)
        return out

    def _should_populate(self, slot: SlotDefinition) -> bool:
        if slot.required:
            return True
        p = self.config.recommended_prob if slot.recommended else self.config.optional_prob
        return self.fake.pyfloat(min_value=0, max_value=1) < p

    def _cardinality(self, slot: SlotDefinition) -> tuple[int, int]:
        lo = slot.minimum_cardinality
        hi = slot.maximum_cardinality
        if lo is None:
            lo = 1 if slot.required else self.config.multivalued_min
        if hi is None:
            hi = max(int(lo), self.config.multivalued_max)
        return int(lo), int(hi)

    @staticmethod
    def _is_identifier(slot: SlotDefinition) -> bool:
        return bool(slot.identifier or slot.key)

    @staticmethod
    def _is_designates_type(slot: SlotDefinition) -> bool:
        return bool(slot.designates_type)

    def _designates_slot(self, cls: str) -> Optional[SlotDefinition]:
        for slot in self.sv.class_induced_slots(cls):
            if slot.designates_type:
                return slot
        return None
