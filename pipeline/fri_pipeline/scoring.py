"""Frozen FEMA December 2024 downstream contract, independently checked in spike #120."""

import numpy as np
import pandas as pd

BANDS = ("Very Low", "Relatively Low", "Relatively Moderate", "Relatively High", "Very High")
SCENARIOS = ("MID_LOWER", "MID_HIGHER", "LATE_LOWER", "LATE_HIGHER")
VARIANTS = ("DRGT", "WFIR", "EXHT_L95", "EXHT_L99", "EXHT_N95", "EXHT_N99")
SUPPORTED = VARIANTS[:4]
FIELDS = ("PALR", "PRISKR", "PRISKS", "DELTAR")


def names(labels: pd.Series) -> pd.Series:
    return labels.astype("string").str.replace(r"\s*\(.*$", "", regex=True).str.strip()


def thresholds(values: pd.Series, labels: pd.Series) -> np.ndarray:
    edges = np.array([values[names(labels) == name].max() for name in BANDS[:-1]], dtype=float)
    if not np.isfinite(edges).all() or not (np.diff(edges) > 0).all():
        raise ValueError("Baseline requires four finite, strictly increasing rating thresholds")
    return edges


def classify(values: pd.Series, edges) -> pd.Series:
    edges = np.asarray(edges)
    if len(edges) != 4 or not np.isfinite(edges).all() or not (np.diff(edges) >= 0).all():
        raise ValueError("Expected four finite nondecreasing thresholds")
    result = pd.Series(pd.NA, index=values.index, dtype="string")
    valid = values.notna()
    result.loc[valid] = np.array(BANDS)[np.searchsorted(edges, values.loc[valid], side="left")]
    return result


def projected_rating(values: pd.Series, baseline: pd.Series, edges) -> pd.Series:
    result = classify(values, edges)
    labels = names(baseline)
    result.loc[labels.isin(["No Expected Annual Losses", "No Rating"])] = "No Rating"
    result.loc[labels.isin(["Insufficient Data", "Not Applicable"])] = "Not Applicable"
    return result


def risk_score(values: pd.Series) -> pd.Series:
    return values.rank(method="average", pct=True) * 100


def display_score(values: pd.Series) -> pd.Series:
    return values.map(lambda value: float(f"{value:.4g}") if pd.notna(value) else np.nan)


def score(master: pd.DataFrame, multipliers: pd.DataFrame) -> pd.DataFrame:
    """Rank the entire frozen population before any geometry/coverage filtering."""
    if not master.index.equals(multipliers.index):
        raise ValueError("Scoring requires the complete baseline population in baseline order")
    result = {}
    for variant in VARIANTS:
        hazard = variant.split("_")[0]
        eal, risk = master[f"{hazard}_EALT"], master[f"{hazard}_RISKV"]
        eal_labels, risk_labels = master[f"{hazard}_EALR"], master[f"{hazard}_RISKR"]
        eal_edges, risk_edges = thresholds(eal, eal_labels), thresholds(risk, risk_labels)
        pooled = pd.concat([multipliers[f"{variant}_{s}_HM"] for s in SCENARIOS])
        hm_edges = pooled.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy()
        for scenario in SCENARIOS:
            prefix = f"{variant}_{scenario}"
            hm = multipliers[f"{prefix}_HM"]
            if not np.isfinite(hm).all() or (hm < 1).any():
                raise ValueError(f"{prefix}: multipliers must be finite and >= 1")
            result[f"{prefix}_HM"] = hm
            result[f"{prefix}_PALT"] = eal * hm
            result[f"{prefix}_PRISKV"] = risk * hm
            result[f"{prefix}_PALR"] = projected_rating(eal * hm, eal_labels, eal_edges)
            result[f"{prefix}_PRISKR"] = projected_rating(risk * hm, risk_labels, risk_edges)
            result[f"{prefix}_PRISKS"] = display_score(risk_score(risk * hm))
            result[f"{prefix}_DELTAR"] = classify(hm, hm_edges)
    return pd.DataFrame(result, index=master.index)


def reproduce_archive(master: pd.DataFrame) -> dict:
    computed = score(master, master)
    checks = []
    for variant in VARIANTS:
        for scenario in SCENARIOS:
            for field in FIELDS:
                column = f"{variant}_{scenario}_{field}"
                expected = master[column] if field == "PRISKS" else names(master[column])
                actual = computed[column]
                matches = (actual.isna() & expected.isna()) | actual.eq(expected).fillna(False)
                checks.append(
                    {"field": column, "compared": len(master), "mismatches": int((~matches).sum())}
                )
    mismatches = sum(row["mismatches"] for row in checks)
    if mismatches:
        raise ValueError(f"Archive regression failed: {mismatches} mismatches")
    return {
        "comparisons": sum(row["compared"] for row in checks),
        "mismatches": mismatches,
        "checks": checks,
    }
