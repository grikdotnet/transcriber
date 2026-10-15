from __future__ import annotations

import json

import pytest

from transcriber.protocol.diarization_json import (
    DiarizationDocument,
    DiarizationInterval,
    DiarizationTimeBase,
    decode_diarization,
    encode_diarization,
)

EMPTY = (
    b'{"schema_version":1,"time_base":{"unit":"sample","sample_rate_hz":16000,'
    b'"start_inclusive":true,"end_exclusive":true},"intervals":[]}\n'
)


def test_canonical_empty_and_nonempty_bytes() -> None:
    assert encode_diarization(DiarizationDocument(())) == EMPTY
    document = DiarizationDocument((DiarizationInterval(7, 10, 30), DiarizationInterval(2, 20, 40)))
    expected = EMPTY.replace(
        b'"intervals":[]',
        b'"intervals":[{"speaker_id":7,"start_sample":10,"end_sample":30},'
        b'{"speaker_id":2,"start_sample":20,"end_sample":40}]',
    )
    assert encode_diarization(document) == expected
    assert decode_diarization(expected) == document
    assert decode_diarization(EMPTY.decode("utf-8")) == DiarizationDocument(())


@pytest.mark.parametrize("section", ["root", "time_base", "interval"])
@pytest.mark.parametrize("change", ["extra", "missing"])
def test_closed_objects(section: str, change: str) -> None:
    value = json.loads(EMPTY)
    value["intervals"] = [{"speaker_id": 1, "start_sample": 0, "end_sample": 10}]
    target = value if section == "root" else (
        value["time_base"] if section == "time_base" else value["intervals"][0]
    )
    if change == "extra":
        target["mode"] = "fallback"
    else:
        del target[next(iter(target))]
    with pytest.raises(ValueError):
        decode_diarization(json.dumps(value))


@pytest.mark.parametrize("field", ["speaker_id", "start_sample", "end_sample"])
@pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
def test_interval_integers_exclude_boolean(field: str, bad: object) -> None:
    interval = {"speaker_id": 1, "start_sample": 0, "end_sample": 10}
    interval[field] = bad
    value = json.loads(EMPTY)
    value["intervals"] = [interval]
    with pytest.raises(ValueError):
        decode_diarization(json.dumps(value))


@pytest.mark.parametrize("field,bad", [
    ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
    ("unit", "seconds"), ("sample_rate_hz", True), ("sample_rate_hz", 16000.0),
    ("sample_rate_hz", 8000), ("start_inclusive", 1), ("start_inclusive", False),
    ("end_exclusive", 1), ("end_exclusive", False),
])
def test_constants(field: str, bad: object) -> None:
    value = json.loads(EMPTY)
    target = value if field == "schema_version" else value["time_base"]
    target[field] = bad
    with pytest.raises(ValueError):
        decode_diarization(json.dumps(value))


@pytest.mark.parametrize("rows", [
    [(0, 0, 10)], [(-1, 0, 10)], [(1, -1, 10)], [(1, 10, 10)], [(1, 11, 10)],
    [(1, 10, 20), (2, 0, 5)], [(2, 0, 10), (1, 0, 5)],
    [(1, 0, 10), (1, 10, 20)], [(1, 0, 20), (2, 5, 10), (1, 15, 30)],
])
def test_rejects_noncanonical_intervals(rows: list[tuple[int, int, int]]) -> None:
    with pytest.raises(ValueError):
        DiarizationDocument(tuple(DiarizationInterval(*row) for row in rows))


@pytest.mark.parametrize("payload", [b"\xff", "{", "null", "[]", '{"schema_version":NaN}',
                                         EMPTY.replace(b'"intervals":[]', b'"intervals":{}')])
def test_rejects_malformed_input(payload: str | bytes) -> None:
    with pytest.raises(ValueError):
        decode_diarization(payload)


def test_constructor_validates_constants_and_collection() -> None:
    with pytest.raises(ValueError):
        DiarizationDocument((), schema_version=True)
    with pytest.raises(ValueError):
        DiarizationDocument((), time_base=DiarizationTimeBase(sample_rate_hz=8000))
    with pytest.raises(ValueError):
        DiarizationDocument([])  # type: ignore[arg-type]


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(ValueError):
        decode_diarization(EMPTY.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1'))
