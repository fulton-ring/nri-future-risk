from pathlib import Path

import pytest

from fri_pipeline.prepare import loca_pieces, record_source, verify_reference


def test_loca_pieces_cover_each_requested_day_once():
    pieces = loca_pieces("ssp245", "2045-2074")
    for period, first, stop in [
        ("MID", "2045-01-01", "2066-01-01"),
        ("LATE", "2070-01-01", "2075-01-01"),
    ]:
        import numpy as np

        selected = [p for p in pieces if p["period"] == period]
        lo = int((np.datetime64(first) - np.datetime64("2045-01-01")).astype(int))
        hi = int((np.datetime64(stop) - np.datetime64("2045-01-01")).astype(int))
        assert selected[0]["days"][0] == lo
        assert selected[-1]["days"][1] == hi
        assert all(
            a["days"][1] == b["days"][0] for a, b in zip(selected, selected[1:], strict=False)
        )


def test_source_fingerprint_is_real_and_rejects_changed_payload(tmp_path):
    raw = tmp_path / "input.nc"
    raw.write_bytes(b"actual downloaded bytes")
    record = record_source(tmp_path / "sources", "https://example.org/input.nc", raw)
    import hashlib

    assert record["sha256"] == hashlib.sha256(raw.read_bytes()).hexdigest()
    raw.write_bytes(b"different version during the same run")
    with pytest.raises(ValueError, match="changed"):
        record_source(tmp_path / "sources", "https://example.org/input.nc", raw)


def test_vendored_reference_hashes_are_checked_before_import():
    verify_reference(Path(__file__).resolve().parents[1] / "vendor" / "fri_rebuild")
