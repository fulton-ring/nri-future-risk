"""Exercise real hazard functions through Hamilton with a tiny, synthetic climate grid."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from fri_pipeline.candidate import build_candidate, verify_candidate
from fri_pipeline.snapshot import CONTRACT, EXCLUDED, SPANS, Snapshot, read_master


def prepared_snapshot(root):
    root.mkdir()
    master = read_master()
    ids = master.loc[~master.STATEABBRV.isin(EXCLUDED)].index
    artifacts = {}

    def register(name, suffix):
        path = root / f"{name}.{suffix}"
        artifacts[name] = {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "sourceIds": ["synthetic"],
        }

    (root / "county_ids.json").write_text(json.dumps(ids.tolist()))
    register("county_ids", "json")
    for name in ("nex_weights", "loca2_weights"):
        sparse.save_npz(root / f"{name}.npz", sparse.csr_matrix(np.ones((len(ids), 1))))
        register(name, "npz")
    pd.DataFrame({"lat": [35.0], "lon": [-100.0]}).to_csv(root / "nex_coordinates.csv", index=False)
    register("nex_coordinates", "csv")
    pd.DataFrame({"nonburnable": 0.2, "grass": 0.8}, index=ids).to_csv(
        root / "fuel_shares.csv", index_label="STCOFIPS"
    )
    register("fuel_shares", "csv")
    months = pd.date_range("1950-01-01", "2100-12-01", freq="MS")
    t = np.arange(len(months))
    for ssp in ("ssp245", "ssp585"):
        for variable in ("tas", "pr"):
            values = (
                20 + 7 * np.sin(t * 2 * np.pi / 12) + 0.005 * t
                if variable == "tas"
                else 3 + np.cos(t * 2 * np.pi / 12) + 0.5 * np.sin(t / 23)
            )
            name = f"monthly_{variable}_{ssp}"
            np.savez(root / f"{name}.npz", values=values[:, None], months=months.to_numpy())
            register(name, "npz")
    edges = np.concatenate([[-np.inf], np.arange(-10.0, 40.05, 0.1), [np.inf]])
    for scenario, period in [
        ("historical", "historical"),
        *[(s, p) for s in ("ssp245", "ssp585") for p in ("MID", "LATE")],
    ]:
        first, last = SPANS[period]
        name = f"fwi_{scenario}_{period}"
        np.savez(
            root / f"{name}.npz",
            values=np.ones((last - first + 1, 1)),
            years=np.arange(first, last + 1),
        )
        register(name, "npz")
        days = len(pd.date_range(f"{first}-01-01", f"{last}-12-31"))
        counts = np.zeros((len(edges), 1), dtype=int)
        counts[300, 0], counts[400, 0] = days - 1000, 1000
        name = f"loca2_{scenario}_{period}"
        np.savez(root / f"{name}.npz", edges=edges, counts=counts)
        register(name, "npz")
    manifest = {
        "schemaVersion": 1,
        "coverage": "CONUS",
        "methodology": CONTRACT["id"],
        "rebuildCommit": CONTRACT["rebuildCommit"],
        "sources": [
            {
                "id": "synthetic",
                "title": "Synthetic test grid; never publish",
                "url": "https://example.org/fixture",
                "sha256": "a" * 64,
                "retrievedAt": "2026-10-24",
            }
        ],
        "artifacts": artifacts,
    }
    path = root / "snapshot.json"
    path.write_text(json.dumps(manifest))
    return path


def test_prepared_climate_runs_all_hazards_and_scoring(tmp_path, monkeypatch):
    snapshot = prepared_snapshot(tmp_path / "inputs")
    result = build_candidate(
        tmp_path / "output", "climate-test", snapshot=str(snapshot), code_revision="a" * 40
    )
    assert result["publishable"] is True
    verify_candidate(tmp_path / "output", publication=True)
    provenance = json.loads((tmp_path / "output/provenance.json").read_text())
    assert np.isfinite(provenance["parameters"]["wildfireElasticity"])
    values = json.loads((tmp_path / "output/counties.json").read_text())
    assert "DRGT_MID_LOWER_PALT" in values["columns"]
    assert "WFIR_LATE_HIGHER_PRISKV" in values["columns"]
    from fri_pipeline import publication

    # The external write is the only substituted boundary; source verification still runs.
    requests = []

    def capture_upload(path, uri):
        if path.name == "request.json":
            requests.append((uri, json.loads(path.read_text())))

    monkeypatch.setattr(publication, "upload", capture_upload)
    request = publication.stage(
        tmp_path / "output",
        "gs://staging",
        "v20261024T120000Z",
        "gs://receipts/climate-test/receipt.json",
    )
    assert request["sourceUri"].startswith("gs://staging/future-risk-index/county-risk/counties/")
    assert request["collection_slug"] == "future-risk-index"
    assert request["sourceDatasets"][0]["sha256"] == CONTRACT["workbookSha256"]
    assert len(requests) == 1


def test_missing_fwi_years_fail_before_projection(tmp_path):
    path = prepared_snapshot(tmp_path / "inputs")
    data = json.loads(path.read_text())
    spec = data["artifacts"]["fwi_historical_historical"]
    artifact = path.parent / spec["path"]
    np.savez(artifact, values=np.ones((29, 1)), years=np.arange(1977, 2006))
    spec["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing years"):
        Snapshot(path).fwi("historical", "historical", "FWI_P95", "MME75")
