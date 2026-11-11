import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from fri_pipeline import current_flow
from fri_pipeline.scoring import BANDS


@pytest.mark.parametrize("missing_tract", [False, True])
def test_hamilton_uses_single_county_gamma_and_separate_national_rankings(
    monkeypatch, missing_tract
):
    class Inputs(current_flow.GeographySnapshot):
        def __init__(self, geography):
            self.full_baseline = pd.DataFrame(
                {"STATEABBRV": ["AL"] * 5 + ["AK"]},
                index=pd.Index([f"0100{i}" for i in range(5)] + ["02013"]),
            )
            self.full_baseline.attrs["geography"] = geography
            for hazard in ("DRGT", "WFIR", "EXHT"):
                for suffix in ("EALT", "RISKV"):
                    self.full_baseline[f"{hazard}_{suffix}"] = np.arange(1.0, 7.0)
                for suffix in ("EALR", "RISKR"):
                    self.full_baseline[f"{hazard}_{suffix}"] = list(BANDS) + ["Very High"]
            self.coverage_diagnostics = {}

        def county_weights(self):
            return sparse.eye(5).tocsr(), self.full_baseline.index[:5]

    counties, tracts = Inputs("county"), Inputs("tract")
    if missing_tract:
        tracts.coverage_diagnostics = {
            "nex-monthly": {"unsupportedAreaIds": [tracts.full_baseline.index[0]]}
        }
    calls = []

    def fit(historic, inputs):
        calls.append(inputs.full_baseline.attrs["geography"])
        return 2.0

    def hm(inputs, variants, gamma=None):
        if gamma is not None:
            assert gamma == 2.0
        result = pd.DataFrame(
            2.0,
            index=inputs.full_baseline.index[:5],
            columns=[f"{v}_{s}_HM" for v in variants for s in current_flow.SCENARIOS],
        )
        if missing_tract and inputs is tracts and variants == ["DRGT"]:
            result.iloc[0] = np.nan
        return result

    monkeypatch.setattr(current_flow.wildfire, "period_fwi", lambda *args: np.ones(5))
    monkeypatch.setattr(current_flow.wildfire, "elasticity", fit)
    monkeypatch.setattr(
        current_flow.wildfire,
        "hazard_multipliers",
        lambda inputs, gamma: hm(inputs, ["WFIR"], gamma),
    )
    monkeypatch.setattr(
        current_flow.drought, "hazard_multipliers", lambda inputs: hm(inputs, ["DRGT"])
    )
    monkeypatch.setattr(
        current_flow.heat, "hazard_multipliers", lambda inputs: hm(inputs, ["EXHT_L95", "EXHT_L99"])
    )
    result = current_flow.run(counties, tracts)
    assert calls == ["county"]
    assert result["parameters"]["wildfireElasticity"] == 2
    assert len(result["tracts"]["scored"]) == 6
    if missing_tract:
        assert result["tracts"]["scored"].DRGT_MID_LOWER_PRISKS.iloc[1] == 25
        assert (
            result["tracts"]["validation"]["projectionCoverage"]["DRGT"]["projectedAreaCount"] == 4
        )
    else:
        assert result["tracts"]["scored"].DRGT_MID_LOWER_PRISKS.iloc[0] == 20
