from pathlib import Path

import pytest

from fri_pipeline.prepare import download_raw, loca_pieces, record_source, verify_reference


@pytest.mark.parametrize("transfer", ["complete", "short", "changed-version"])
def test_parallel_download_preserves_bytes_and_pins_source_version(tmp_path, monkeypatch, transfer):
    import requests

    from fri_pipeline import prepare

    payload = b"0123456789abcdefghijklmnopqrstuvwxyz"
    head = requests.Response()
    head.status_code = 200
    head.headers.update({"Content-Length": str(len(payload)), "ETag": '"fixed-version"'})
    monkeypatch.setattr(prepare.requests, "head", lambda *a, **kw: head)
    monkeypatch.setattr(prepare.time, "sleep", lambda _: None)
    calls = []

    def get(url, *, headers, **kwargs):
        assert headers["If-Match"] == '"fixed-version"'
        first, last = map(int, headers["Range"].removeprefix("bytes=").split("-"))
        calls.append((first, last))
        r = requests.Response()
        r.status_code = 206
        r.headers.update(
            {"Content-Range": f"bytes {first}-{last}/{len(payload)}", "ETag": '"fixed-version"'}
        )
        r._content, r._content_consumed = payload[first : last + 1], True
        if transfer == "short" and first == 0:
            r._content = r._content[:-1]
        if transfer == "changed-version":
            r.headers["ETag"] = '"new-version"'
        return r

    monkeypatch.setattr(prepare.requests, "get", get)
    monkeypatch.setenv("FRI_CACHE", str(tmp_path))
    target = tmp_path / "source.nc"
    if transfer == "changed-version":
        with pytest.raises(ValueError, match="version"):
            prepare.download_loca2("https://example.org/input.nc", target)
        assert not target.exists()
        return
    assert prepare.download_loca2("https://example.org/input.nc", target).read_bytes() == payload
    assert len(calls) == (5 if transfer == "short" else 4)


def test_download_retries_server_failure_and_records_only_complete_source(tmp_path, monkeypatch):
    import requests

    from fri_pipeline import prepare

    def response(status, payload):
        result = requests.Response()
        result.status_code = status
        result._content = payload
        result._content_consumed = True
        return result

    responses = iter([response(500, b"server error"), response(200, b"complete source")])
    monkeypatch.setenv("FRI_CACHE", str(tmp_path))
    monkeypatch.setattr(prepare.requests, "get", lambda *a, **kw: next(responses))
    monkeypatch.setattr(prepare.time, "sleep", lambda _: None)
    target = tmp_path / "input.nc"
    assert download_raw("https://example.org/input.nc", target).read_bytes() == b"complete source"
    records = list((tmp_path / "sources").glob("*.json"))
    assert len(records) == 1


def test_download_rejects_partial_response(tmp_path, monkeypatch):
    import requests

    from fri_pipeline import prepare

    response = requests.Response()
    response.status_code = 206
    response._content = b"partial source"
    response._content_consumed = True
    monkeypatch.setenv("FRI_CACHE", str(tmp_path))
    monkeypatch.setattr(prepare.requests, "get", lambda *a, **kw: response)
    with pytest.raises(ValueError, match="206"):
        download_raw("https://example.org/input.nc", tmp_path / "input.nc")
    assert not (tmp_path / "input.nc").exists()


def test_download_stops_after_four_server_failures(tmp_path, monkeypatch):
    from unittest.mock import Mock

    import requests

    from fri_pipeline import prepare

    response = requests.Response()
    response.status_code = 500
    response._content = b""
    response._content_consumed = True
    get = Mock(return_value=response)
    monkeypatch.setenv("FRI_CACHE", str(tmp_path))
    monkeypatch.setattr(prepare.requests, "get", get)
    monkeypatch.setattr(prepare.time, "sleep", lambda _: None)
    with pytest.raises(requests.HTTPError):
        download_raw("https://example.org/input.nc", tmp_path / "input.nc")
    assert get.call_count == 4
    assert not (tmp_path / "input.nc").exists()


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
