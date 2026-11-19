"""Circularity guard on the pilot table: every registry date, status and capacity field is dropped."""

import pandas as pd

from bo.data import pilot
from bo.data.registry import registry_columns


def test_pilot_registry_fields_are_all_prefixed_and_dropped():
    raw = pd.DataFrame(
        {
            "pilot_id": ["Q000"],
            "subtype": ["battery"],
            "lat": [52.0],
            "lon": [13.0],
            "status": ["In Betrieb"],
            "commissioned": [pd.Timestamp("2025-03-01")],
            "planned": [False],
            "size_class": ["5-20 MW"],
            "power_kw": [12_000.0],
        }
    )
    renamed = raw.rename(columns=pilot.REG_RENAME)
    dropped = set(registry_columns(renamed))
    assert dropped == {"reg_status", "reg_commissioning_date", "reg_planned",
                       "reg_size_class", "reg_power_kw"}
    features = renamed.drop(columns=list(dropped))
    assert not {"status", "commissioned", "planned", "size_class", "power_kw"} & set(features.columns)


def test_capacity_derived_flags_and_unit_counts_are_dropped():
    df = pd.DataFrame(columns=[
        "site_id", "lat", "lon", "flag_power_missing_any", "flag_kwh_implausible_duration_any",
        "flag_net_gt_gross_any", "n_units", "n_units_with_coords", "n_locations",
        "flag_coord_missing_any",
    ])
    dropped = set(registry_columns(df))
    assert {"flag_power_missing_any", "flag_kwh_implausible_duration_any", "flag_net_gt_gross_any",
            "n_units", "n_units_with_coords", "n_locations"} <= dropped
    assert not {"site_id", "lat", "lon", "flag_coord_missing_any"} & dropped
