from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import pytest

from transcriber.protocol.firered_probabilities import decode_probability_document

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "vendor" / "firered-vad-ncnn"
MODEL_DIR = ROOT / "models" / "firered-vad.ncnn"
SAMPLE = ROOT / "fixtures" / "sample" / "prepared.wav"
FRONTEND = ROOT / "third_party" / "firered-vad" / "runtime-common-frontend"


def _argv(audio: Path, **overrides: Path) -> tuple[str, ...]:
    paths = {
        "model_param": MODEL_DIR / "firered_vad_non_stream.ncnn.param",
        "model_bin": MODEL_DIR / "firered_vad_non_stream.ncnn.bin",
        "cmvn_means": MODEL_DIR / "cmvn_means.bin",
        "cmvn_istd": MODEL_DIR / "cmvn_istd.bin",
    }
    paths.update(overrides)
    return (
        str(RUNNER),
        "--audio",
        str(audio.resolve()),
        "--model-param",
        str(paths["model_param"].resolve()),
        "--model-bin",
        str(paths["model_bin"].resolve()),
        "--cmvn-means",
        str(paths["cmvn_means"].resolve()),
        "--cmvn-istd",
        str(paths["cmvn_istd"].resolve()),
        "--chunk-max-frames",
        "30000",
    )


def _run(audio: Path, **overrides: Path) -> subprocess.CompletedProcess[str]:
    assert RUNNER.is_file(), "native runner has not been built"
    return subprocess.run(_argv(audio, **overrides), text=True, capture_output=True, check=False)


def _assert_coherent_document(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout.endswith("\n")
    assert completed.stdout.count("\n") == 1
    document = decode_probability_document(completed.stdout)
    assert document.frames.frame_count == len(document.frames.probabilities)


def test_pinned_frontend_manifest_matches_compiled_sources() -> None:
    manifest = json.loads((ROOT / "third_party" / "firered-vad" / "manifest.json").read_text())
    assert manifest["revision"] == "c30ec49e8cc69642b0ee65362eba11b9d11c6e54"
    for relative, expected in manifest["runtime_common_frontend_sha256"].items():
        assert hashlib.sha256((FRONTEND / relative).read_bytes()).hexdigest() == expected
    cmake = (ROOT / "native" / "firered_vad_ncnn" / "CMakeLists.txt").read_text()
    assert "third_party/firered-vad/runtime-common-frontend" in cmake
    assert '"${UPSTREAM_FRONTEND}/fft.cc"' in cmake
    example = manifest["runtime_ncnn_example"]
    example_path = ROOT / "third_party" / "firered-vad" / example["path"]
    assert hashlib.sha256(example_path.read_bytes()).hexdigest() == example["sha256"]

    native_root = ROOT / "native" / "firered_vad_ncnn"
    adapter = (native_root / "infrastructure" / "upstream_cmvn_adapter.cpp").read_text()
    frontend_adapter = (native_root / "infrastructure" / "firered_frontend_adapter.cpp").read_text()
    assert "infrastructure/upstream_cmvn_adapter.cpp" in cmake
    assert example["path"] in adapter
    assert "load_binary_vector" in adapter
    assert "apply_cmvn" in adapter
    assert "ApplyPinnedCmvn" in frontend_adapter
    assert "(value - means[dimension]) * istd[dimension]" not in frontend_adapter

    forwarding = {
        name: (native_root / "frontend" / name).read_text()
        for name in ("fbank.h", "fft.h", "wav.h")
    }
    for name, source in forwarding.items():
        assert f"runtime-common-frontend/{name}" in source


def test_supplied_prepared_wav_is_accepted_and_emits_one_coherent_document() -> None:
    _assert_coherent_document(_run(SAMPLE))


def test_controlled_noncanonical_wav_is_rejected_at_runner_boundary(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0\0\0\0" * 400)

    completed = _run(path)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert "audio" in completed.stderr.lower()


def test_controlled_ieee_float_format_code_is_rejected_at_runner_boundary(tmp_path: Path) -> None:
    path = tmp_path / "float-format-code.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0\0" * 400)
    encoded = bytearray(path.read_bytes())
    encoded[20:22] = (3).to_bytes(2, "little")
    path.write_bytes(encoded)

    completed = _run(path)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert "audio" in completed.stderr.lower()


def test_ncnn_adapter_requires_exact_logical_output_count() -> None:
    source = (
        ROOT
        / "native"
        / "firered_vad_ncnn"
        / "infrastructure"
        / "ncnn_inference.cpp"
    ).read_text()
    assert "LogicalElementCount(result) != static_cast<std::size_t>(count)" in source
    assert "result.total() < static_cast<std::size_t>(count)" not in source


@pytest.mark.parametrize("asset", ["model_param", "model_bin", "cmvn_means", "cmvn_istd"])
def test_missing_supplied_asset_is_classified(asset: str, tmp_path: Path) -> None:
    completed = _run(SAMPLE, **{asset: tmp_path / "missing"})

    assert completed.returncode == 4
    assert completed.stdout == ""
    assert "asset" in completed.stderr.lower()


def test_long_input_reports_exactly_the_serialized_probability_count(tmp_path: Path) -> None:
    path = tmp_path / "over-30000-frames.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0\0" * 4_800_400)

    _assert_coherent_document(_run(path))
