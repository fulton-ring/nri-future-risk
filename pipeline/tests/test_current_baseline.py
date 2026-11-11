import zipfile

import numpy as np
import pandas as pd
import pytest

from fri_pipeline import current_baseline as cb
from fri_pipeline import current_flow as cf
from fri_pipeline.scoring import BANDS, SCENARIOS, SUPPORTED


def baseline():
    frame = pd.DataFrame(
        {"STATEABBRV": ["AL"] * 5 + ["AK"]},
        index=pd.Index(["01001", "01003", "01005", "01007", "01009", "02013"], name="STCOFIPS"),
    )
    for hazard in ("DRGT", "WFIR", "EXHT"):
        frame[f"{hazard}_EALT"] = [1.0, 2.0, 3.0, 4.0, 5.0, np.nan]
        frame[f"{hazard}_RISKV"] = [10.0, 20.0, 30.0, 40.0, 50.0, np.nan]
        frame[f"{hazard}_EALR"] = list(BANDS) + ["Not Applicable"]
        frame[f"{hazard}_RISKR"] = list(BANDS) + ["Insufficient Data"]
    return frame


def test_load_preserves_native_ids_nulls_and_maps_heat(tmp_path):
    raw = baseline().reset_index().rename(columns=lambda c: c.replace("EXHT_", "HWAV_"))
    raw["NRI_VER"] = "December 2025"
    path = tmp_path / "nri.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("NRI_Table_Counties.csv", raw.to_csv(index=False))
    frame = cb.load_baseline(path, "county", validate_population=False)
    assert frame.index.equals(baseline().index)
    assert frame.EXHT_EALT.isna().iloc[-1]
    assert "HWAV_EALT" not in frame
    assert frame.attrs["sourceSha256"]
    raw.loc[0, "NRI_VER"] = "December 2024"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("NRI_Table_Counties.csv", raw.to_csv(index=False))
    with pytest.raises(ValueError, match="December 2025"):
        cb.load_baseline(path, "county", validate_population=False)


@pytest.mark.parametrize("ids", [["01001", "01001"], ["1001", "01003"], ["01001000000", "01003"]])
def test_rejects_bad_native_ids(ids):
    with pytest.raises(ValueError, match="IDs"):
        cb.validate_ids(pd.Index(ids), "county")


def test_tract_ids_match_native_county():
    raw = pd.DataFrame(
        {
            "TRACTFIPS": ["09110010100"],
            "STCOFIPS": ["09110"],
            "STATEABBRV": ["CT"],
            "NRI_VER": ["December 2025"],
        }
    )
    for h in ("DRGT", "WFIR", "HWAV"):
        for f in ("EALT", "RISKV", "EALR", "RISKR"):
            raw[f"{h}_{f}"] = 1 if f in ("EALT", "RISKV") else "Very Low"
    frame = cb.normalize_baseline(raw, "tract", validate_population=False)
    assert frame.index.tolist() == ["09110010100"]
    raw["STCOFIPS"] = "09001"
    with pytest.raises(ValueError, match="county"):
        cb.normalize_baseline(raw, "tract", validate_population=False)


def test_scoring_national_population_and_null_status():
    master = baseline()
    cols = [f"{h}_{s}_HM" for h in SUPPORTED for s in SCENARIOS]
    updates = pd.DataFrame(2.0, index=master.index[:-1], columns=cols)
    hm = cf.complete_multipliers(master, updates)
    assert hm.iloc[-1].isna().all()
    scored, bins, validation = cf.score_geography(master, hm)
    assert scored.DRGT_MID_LOWER_PALT.iloc[0] == 2
    assert np.isnan(scored.DRGT_MID_LOWER_PALT.iloc[-1])
    assert pd.isna(scored.DRGT_MID_LOWER_PRISKR.iloc[-1])
    assert scored.DRGT_MID_LOWER_PRISKS.iloc[0] == 20
    assert bins["DRGT"]["eal"] == [1, 2, 3, 4]
    assert validation["population"] == 6
    tract = master.copy()
    tract.loc[tract.index[0], "DRGT_EALT"] = 0.1
    ts, tb, _ = cf.score_geography(tract, hm)
    assert ts.DRGT_MID_LOWER_PALT.iloc[0] == 0.2
    assert tb["DRGT"]["eal"][0] == 0.1
    updates.iloc[0, 0] = 0.99
    with pytest.raises(ValueError, match=">= 1"):
        cf.complete_multipliers(master, updates)


def test_tract_population_requires_complete_national_and_conus_inventory():
    ids = [f"{county}000100" for county in sorted(cb.CT_COUNTIES)]
    ids += [f"01001{i:06d}" for i in range(83481 - len(ids))]
    ids += [f"02013{i:06d}" for i in range(85154 - len(ids))]
    raw = pd.DataFrame(
        {
            "TRACTFIPS": ids,
            "STCOFIPS": [identifier[:5] for identifier in ids],
            "STATEABBRV": ["CT"] * 9 + ["AL"] * (83481 - 9) + ["AK"] * (85154 - 83481),
            "NRI_VER": cb.RELEASE,
        }
    )
    for hazard in ("DRGT", "WFIR", "HWAV"):
        for field in ("EALT", "RISKV", "EALR", "RISKR"):
            raw[f"{hazard}_{field}"] = 1 if field in ("EALT", "RISKV") else "Very Low"
    assert len(cb.normalize_baseline(raw, "tract")) == 85154
    with pytest.raises(ValueError, match="85154 national / 83481 CONUS"):
        cb.normalize_baseline(raw.iloc[:-1], "tract")
    wrong_conus = raw.copy()
    wrong_conus.loc[9, "STATEABBRV"] = "AK"
    with pytest.raises(ValueError, match="85154 national / 83481 CONUS"):
        cb.normalize_baseline(wrong_conus, "tract")
    sample = cb.normalize_baseline(raw.iloc[:9], "tract", validate_population=False)
    assert sample.index.tolist() == ids[:9]
