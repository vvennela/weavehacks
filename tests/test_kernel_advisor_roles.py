from sera.kernel_advisor_roles import (
    ADVISOR_ROLES,
    ALTERNATE_ADVISOR_IDS,
    DEFAULT_ADVISOR_IDS,
)


def test_default_advisor_roster_has_fifteen_unique_available_ids():
    assert len(DEFAULT_ADVISOR_IDS) == 15
    assert len(set(DEFAULT_ADVISOR_IDS)) == 15
    assert set(DEFAULT_ADVISOR_IDS) <= set(ADVISOR_ROLES)


def test_alternate_advisor_ids_are_available_and_not_in_default_roster():
    assert ALTERNATE_ADVISOR_IDS
    assert len(set(ALTERNATE_ADVISOR_IDS)) == len(ALTERNATE_ADVISOR_IDS)
    assert set(ALTERNATE_ADVISOR_IDS) <= set(ADVISOR_ROLES)
    assert not set(ALTERNATE_ADVISOR_IDS) & set(DEFAULT_ADVISOR_IDS)


def test_every_advisor_role_has_a_fixed_nonempty_description():
    assert all(isinstance(role_id, str) and role_id for role_id in ADVISOR_ROLES)
    assert all(isinstance(description, str) and description.strip()
               for description in ADVISOR_ROLES.values())


def test_fp32_sme_tile_role_respects_four_available_za_tiles():
    description = ADVISOR_ROLES["sme_fp32_tiles"].lower()
    assert "four" in description
    assert "eight" in description
    assert "fp32" in description
