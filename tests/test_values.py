"""Unit tests for identifier minting (see values.ValueFactory)."""

from __future__ import annotations

from faker import Faker

from linkml_data_gen.values import ValueFactory


def test_mint_id_unique_across_classes_sharing_4cap_prefix():
    """Regression test: classes whose names agree on their first 4 capital
    letters (e.g. ATACSeqAssay / ATACSeqDataset) must not mint colliding ids.
    """
    vf = ValueFactory(Faker(), seed=0)
    assay_ids = [vf.mint_id("ATACSeqAssay") for _ in range(3)]
    dataset_ids = [vf.mint_id("ATACSeqDataset") for _ in range(3)]
    assert not set(assay_ids) & set(dataset_ids)


def test_mint_id_unique_when_abbreviation_letters_fully_exhausted():
    """Even classes whose names produce byte-identical candidate letters at
    every prefix length (no capitals to fall back on) must still disambiguate.
    """
    vf = ValueFactory(Faker(), seed=0)
    sample_id = vf.mint_id("Sample")
    simple_id = vf.mint_id("Simple")
    assert sample_id != simple_id


def test_mint_id_stable_prefix_per_class():
    """The same class always reuses the abbreviation it was first assigned."""
    vf = ValueFactory(Faker(), seed=0)
    first = vf.mint_id("Donor").split("-")[0]
    vf.mint_id("Sample")
    second = vf.mint_id("Donor").split("-")[0]
    assert first == second
