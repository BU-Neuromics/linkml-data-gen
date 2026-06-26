"""Scalar / leaf value generation.

Everything that turns a slot definition into a concrete primitive value lives
here: type-driven generation, slot-name heuristics for realism, regex-pattern
satisfaction, enum selection (static and dynamic), and identifier minting.
"""

from __future__ import annotations

import random
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

import rstr
from faker import Faker
from linkml_runtime.linkml_model.meta import (
    EnumDefinition,
    SlotDefinition,
    TypeDefinition,
)

from .hints import FieldHint

# Returned by ValueFactory.from_hint when a hint shapes no value, so callers
# can distinguish "no instruction" from a legitimately generated ``None``.
_NO_HINT = object()

# LinkML type ``base`` strings -> a coarse generation category.
_BASE_KIND = {
    "str": "string",
    "int": "integer",
    "Decimal": "float",
    "float": "float",
    "Bool": "boolean",
    "bool": "boolean",
    "XSDDate": "date",
    "XSDDateTime": "datetime",
    "XSDTime": "time",
    "URIorCURIE": "uriorcurie",
    "URI": "uri",
    "Curie": "curie",
    "NCName": "string",
    "NodeIdentifier": "uriorcurie",
}

# Slot-name keyword -> Faker-backed string strategy. Checked as substrings so
# ``contact_email`` and ``donor_name`` both match. Order matters: earlier, more
# specific keys win.
_NAME_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("email",), "email"),
    (("url", "uri", "link", "href", "location", "endpoint"), "url"),
    (("phone", "telephone", "fax"), "phone"),
    (("first_name", "given_name", "forename"), "first_name"),
    (("last_name", "family_name", "surname"), "last_name"),
    (("full_name", "person_name"), "person"),
    (("username", "login", "handle"), "username"),
    (("city", "town"), "city"),
    (("country",), "country"),
    (("state", "province"), "state"),
    (("zip", "postal", "postcode"), "postcode"),
    (("address", "street"), "address"),
    (("company", "organization", "organisation", "institution", "vendor", "manufacturer"), "company"),
    (("title", "label", "heading"), "title"),
    (("description", "summary", "abstract", "comment", "note", "narrative", "text"), "sentence"),
    (("color", "colour"), "color"),
    (("version",), "version"),
    (("name",), "name_word"),
    (("id", "identifier", "code", "accession", "key"), "code"),
]


class ValueFactory:
    """Produces leaf values. One instance per generation run (carries the RNG)."""

    def __init__(self, faker: Faker, seed: Optional[int] = None):
        self.fake = faker
        self._id_counters: dict[str, int] = {}
        # rstr.xeger() otherwise draws from the global RNG, which would make
        # pattern-based values (and thus whole runs) non-reproducible.
        self._rstr = rstr.Rstr(random.Random(seed))

    # ----- identifiers -------------------------------------------------------
    @staticmethod
    def _abbrev(class_name: str) -> str:
        """A short uppercase prefix for human-readable ids (Donor -> DNR)."""
        letters = [c for c in class_name if c.isalpha()]
        caps = [c for c in class_name if c.isupper()]
        if len(caps) >= 2:
            stub = "".join(caps[:4])
        else:
            consonants = [c for c in letters[1:] if c.lower() not in "aeiou"]
            stub = (letters[0] + "".join(consonants))[:3] if letters else "X"
        return stub.upper()

    def mint_id(self, class_name: str) -> str:
        """Mint a unique, readable identifier such as ``DNR-0007``."""
        n = self._id_counters.get(class_name, 0) + 1
        self._id_counters[class_name] = n
        return f"{self._abbrev(class_name)}-{n:04d}"

    # ----- hints -------------------------------------------------------------
    def from_hint(self, hint: FieldHint, kind: str) -> Any:
        """Generate a value from an explicit hint, or return ``_NO_HINT``.

        Handles the value-shaping forms (const / choices / faker / pattern /
        numeric distribution / date window). Returns the sentinel when the hint
        carries no value-shaping instruction so the caller can fall through.
        """
        if hint.has_const:
            return hint.const
        if hint.choices is not None:
            return self.weighted_choice(hint.choices, hint.weights)
        if hint.faker:
            return self.faker_value(hint)
        if hint.pattern:
            return self._from_pattern(hint.pattern)
        if hint.distribution and kind in ("integer", "float"):
            return self._sample_numeric(hint, want_int=(kind == "integer"))
        if (hint.date_start or hint.date_end) and kind in ("date", "datetime"):
            return self._hinted_date(hint, kind)
        return _NO_HINT

    def sample_count(self, lo: int, hi: int, dist: Optional[str], lam: Optional[float]) -> int:
        """Sample a cardinality in ``[lo, hi]`` per the requested distribution."""
        lo, hi = int(lo), int(hi)
        if hi < lo:
            lo, hi = hi, lo
        d = (dist or "uniform").lower()
        if d == "fixed":
            return hi
        if d == "poisson":
            mean = lam if lam is not None else (lo + hi) / 2.0
            n = self._poisson(mean)
            return max(lo, min(hi, n))
        return self.fake.random_int(lo, hi)

    def _poisson(self, mean: float) -> int:
        # Knuth's algorithm, using the seeded RNG for reproducibility.
        import math

        if mean <= 0:
            return 0
        limit = math.exp(-mean)
        k, prod = 0, 1.0
        while True:
            k += 1
            prod *= self.fake.random.random()
            if prod <= limit:
                return k - 1

    def weighted_choice(self, choices: list, weights: Optional[list]) -> Any:
        if weights:
            return self.fake.random.choices(choices, weights=weights, k=1)[0]
        return self.fake.random_element(choices)

    def faker_value(self, hint: FieldHint) -> Any:
        method = getattr(self.fake, hint.faker)
        return method(*(hint.faker_args or []), **(hint.faker_kwargs or {}))

    def _sample_numeric(self, hint: FieldHint, want_int: bool) -> Any:
        dist = (hint.distribution or "uniform").lower()
        p = hint.params or {}
        rnd = self.fake.random
        lo = hint.minimum if hint.minimum is not None else 0.0
        hi = hint.maximum if hint.maximum is not None else 1000.0
        v = lo
        for _ in range(100):
            if dist in ("normal", "gauss", "gaussian"):
                mu = p.get("mean", p.get("mu", (lo + hi) / 2))
                v = rnd.gauss(mu, p.get("std", p.get("sigma", 1.0)))
            elif dist in ("lognormal", "lognorm"):
                v = rnd.lognormvariate(p.get("mean", p.get("mu", 0.0)),
                                       p.get("sigma", p.get("std", 1.0)))
            elif dist in ("exponential", "expo", "exp"):
                v = rnd.expovariate(p.get("lam", p.get("rate", 1.0)))
            elif dist in ("triangular", "tri"):
                v = rnd.triangular(lo, hi, p.get("mode", (lo + hi) / 2))
            elif dist in ("int", "int_uniform", "integer"):
                want_int = True
                v = rnd.randint(int(lo), int(hi))
            else:  # uniform
                v = rnd.uniform(lo, hi)
            in_lo = hint.minimum is None or v >= hint.minimum
            in_hi = hint.maximum is None or v <= hint.maximum
            if in_lo and in_hi:
                break
        if hint.minimum is not None:
            v = max(v, hint.minimum)
        if hint.maximum is not None:
            v = min(v, hint.maximum)
        if want_int or hint.integer:
            return int(round(v))
        return round(v, 3)

    def _hinted_date(self, hint: FieldHint, kind: str) -> str:
        start = self._parse_dt(hint.date_start) or self._WINDOW_START
        end = self._parse_dt(hint.date_end) or self._WINDOW_END
        if kind == "date":
            return self.fake.date_between_dates(start.date(), end.date()).isoformat()
        dt = self.fake.date_time_between_dates(start, end).replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @staticmethod
    def _parse_dt(val) -> Optional[datetime]:
        if val is None:
            return None
        s = str(val).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None)  # window bounds are naive
        except ValueError:
            try:
                return datetime.combine(date.fromisoformat(s[:10]), datetime.min.time())
            except ValueError:
                return None

    # ----- enums -------------------------------------------------------------
    def enum_value(self, enum: EnumDefinition, hint: Optional[FieldHint] = None) -> Optional[str]:
        """Pick a permissible value, or synthesize a CURIE for a dynamic enum."""
        pvs = list(enum.permissible_values or {})
        if hint is not None:
            if hint.choices is not None:
                return self.weighted_choice(hint.choices, hint.weights)
            if hint.weights and pvs and len(hint.weights) == len(pvs):
                return self.weighted_choice(pvs, hint.weights)
        if pvs:
            return self.fake.random_element(pvs)
        # Dynamic enum (reachable_from / matches): no static values. Build a
        # plausible CURIE using the prefix of a declared source node.
        rf = getattr(enum, "reachable_from", None)
        nodes = list(getattr(rf, "source_nodes", []) or []) if rf else []
        if nodes:
            sample = str(nodes[0])
            if ":" in sample:
                prefix, ref = sample.split(":", 1)
                width = len(ref) if ref.isdigit() else 7
                return f"{prefix}:{self.fake.numerify('#' * max(width, 1))}"
        # matches / enum_range expression with no usable hint: emit a token.
        return self.fake.bothify("ENUM_???").upper()

    # ----- typed scalars -----------------------------------------------------
    def scalar(
        self,
        slot: SlotDefinition,
        type_def: Optional[TypeDefinition],
        kind_hint: Optional[str] = None,
        hint: Optional[FieldHint] = None,
    ) -> Any:
        """Generate a scalar appropriate to the slot's (resolved) type."""
        kind = kind_hint or self._kind_of(type_def)

        if hint is not None and not hint.is_empty:
            shaped = self.from_hint(hint, kind)
            if shaped is not _NO_HINT:
                return shaped

        if slot.pattern:
            return self._from_pattern(slot.pattern)

        name = (slot.name or "").lower()

        if kind == "string":
            return self._string(name, slot)
        if kind == "integer":
            return self._integer(slot, hint)
        if kind == "float":
            return self._float(slot, hint)
        if kind == "boolean":
            return self.fake.boolean()
        if kind == "date":
            return self._date(slot).isoformat()
        if kind == "datetime":
            return self._datetime(slot).isoformat()
        if kind == "time":
            return self.fake.time()
        if kind in ("uri", "uriorcurie", "curie"):
            return self._uri_like(name, kind)
        # Unknown base: fall back to a short string.
        return self._string(name, slot)

    # ----- helpers -----------------------------------------------------------
    @staticmethod
    def _kind_of(type_def: Optional[TypeDefinition]) -> str:
        if type_def is None:
            return "string"
        base = getattr(type_def, "base", None)
        return _BASE_KIND.get(base, "string")

    def _from_pattern(self, pattern: str) -> str:
        # Anchors confuse the generator; strip leading/trailing ^ $.
        pat = pattern
        if pat.startswith("^"):
            pat = pat[1:]
        if pat.endswith("$"):
            pat = pat[:-1]
        try:
            return self._rstr.xeger(pat)
        except Exception:
            # Last resort: a token that at least looks structured.
            return re.sub(r"[^A-Za-z0-9_-]", "", self.fake.bothify("??##??"))

    def _string(self, name: str, slot: SlotDefinition) -> str:
        for keys, strat in _NAME_HINTS:
            if any(k in name for k in keys):
                return self._by_strategy(strat, slot)
        # No hint: a couple of words reads better than lorem for labels.
        return self.fake.sentence(nb_words=3).rstrip(".")

    def _by_strategy(self, strat: str, slot: SlotDefinition) -> str:
        f = self.fake
        if strat == "email":
            return f.email()
        if strat == "url":
            return f.url()
        if strat == "phone":
            return f.phone_number()
        if strat == "first_name":
            return f.first_name()
        if strat == "last_name":
            return f.last_name()
        if strat == "person":
            return f.name()
        if strat == "username":
            return f.user_name()
        if strat == "city":
            return f.city()
        if strat == "country":
            return f.country()
        if strat == "state":
            return f.state()
        if strat == "postcode":
            return f.postcode()
        if strat == "address":
            return f.street_address()
        if strat == "company":
            return f.company()
        if strat == "title":
            return f.sentence(nb_words=4).rstrip(".")
        if strat == "sentence":
            return f.sentence(nb_words=12).rstrip(".")
        if strat == "color":
            return f.color_name()
        if strat == "version":
            return f"{f.random_int(0, 9)}.{f.random_int(0, 20)}.{f.random_int(0, 9)}"
        if strat == "name_word":
            # Capitalised noun-ish phrase, good for human-readable labels.
            return f"{f.word().capitalize()} {f.word()}"
        if strat == "code":
            return f.bothify("??-####").upper()
        return f.word()

    def _bounds(self, slot: SlotDefinition, hint: Optional[FieldHint], dlo, dhi):
        lo = slot.minimum_value if slot.minimum_value is not None else dlo
        hi = slot.maximum_value if slot.maximum_value is not None else dhi
        if hint is not None:
            if hint.minimum is not None:
                lo = hint.minimum
            if hint.maximum is not None:
                hi = hint.maximum
        return (hi, lo) if lo > hi else (lo, hi)

    def _integer(self, slot: SlotDefinition, hint: Optional[FieldHint] = None) -> int:
        lo, hi = self._bounds(slot, hint, 0, 1000)
        return self.fake.random_int(int(lo), int(hi))

    def _float(self, slot: SlotDefinition, hint: Optional[FieldHint] = None) -> float:
        lo, hi = self._bounds(slot, hint, 0.0, 1000.0)
        return round(self.fake.pyfloat(min_value=float(lo), max_value=float(hi)), 3)

    # Fixed reference window. Using "now"/"today" would make output depend on
    # wall-clock time (datetimes drift by ~1s between calls), breaking
    # seed-based reproducibility. A fixed window keeps runs deterministic.
    _WINDOW_START = datetime(2015, 1, 1)
    _WINDOW_END = datetime(2025, 1, 1)

    def _date(self, slot: SlotDefinition) -> date:
        return self.fake.date_between_dates(
            self._WINDOW_START.date(), self._WINDOW_END.date()
        )

    def _datetime(self, slot: SlotDefinition) -> datetime:
        # Timezone-aware: LinkML's datetime validates as RFC3339, which requires
        # an offset. A naive datetime would fail format checking.
        dt = self.fake.date_time_between_dates(self._WINDOW_START, self._WINDOW_END)
        return dt.replace(tzinfo=timezone.utc)

    def _uri_like(self, name: str, kind: str) -> str:
        if kind == "curie":
            return f"{self.fake.lexify('???').upper()}:{self.fake.numerify('#######')}"
        # uri / uriorcurie: a real-looking URL is broadly valid for both.
        return self.fake.uri()
