from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build-firered-vad-ncnn-macos.sh"
CMAKE = ROOT / "native" / "firered_vad_ncnn" / "CMakeLists.txt"


def test_build_wrapper_requires_explicit_ncnn_root_and_has_no_download_step() -> None:
    text = SCRIPT.read_text()
    assert SCRIPT.stat().st_mode & 0o111
    assert "NCNN_ROOT" in text
    assert not any(term in text for term in ("curl ", "wget ", "git clone"))
    environment = {key: value for key, value in os.environ.items() if key != "NCNN_ROOT"}

    completed = subprocess.run(
        [str(SCRIPT)], cwd=ROOT, env=environment, text=True, capture_output=True, check=False
    )

    assert completed.returncode != 0
    assert "NCNN_ROOT" in completed.stderr


def test_distribution_metadata_pins_dependencies() -> None:
    firered = json.loads((ROOT / "third_party" / "firered-vad" / "manifest.json").read_text())
    ncnn = json.loads((ROOT / "third_party" / "ncnn" / "manifest.json").read_text())
    assert firered["revision"] == "c30ec49e8cc69642b0ee65362eba11b9d11c6e54"
    assert ncnn["tag"] == "20260113"
    assert ncnn["revision"] == "e956fbf9bd97fe945df35d736747dc816f8b5f42"
    assert (ROOT / "native" / "firered_vad_ncnn" / "LICENSE").is_file()
    assert (ROOT / "native" / "firered_vad_ncnn" / "NOTICE.md").is_file()


def test_cmake_requires_exact_static_ncnn_install_and_version_pin(tmp_path: Path) -> None:
    text = CMAKE.read_text()

    assert 'set(NCNN_LIBRARY "${NCNN_ROOT}/lib/libncnn.a")' in text
    assert 'set(NCNN_VERSION_FILE "${NCNN_ROOT}/lib/cmake/ncnn/ncnnConfigVersion.cmake")' in text
    assert 'set(NCNN_REQUIRED_VERSION "20260113")' in text
    assert "find_library" not in text

    fake_root = tmp_path / "ncnn"
    (fake_root / "include" / "ncnn").mkdir(parents=True)
    (fake_root / "include" / "ncnn" / "net.h").touch()
    (fake_root / "lib" / "cmake" / "ncnn").mkdir(parents=True)
    (fake_root / "lib" / "libncnn.a").touch()
    (fake_root / "lib" / "cmake" / "ncnn" / "ncnnConfigVersion.cmake").write_text(
        'set(PACKAGE_VERSION "wrong-version")\n'
    )

    completed = subprocess.run(
        [
            "cmake",
            "-S",
            str(ROOT / "native" / "firered_vad_ncnn"),
            "-B",
            str(tmp_path / "build"),
            f"-DNCNN_ROOT={fake_root}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "expected pinned version 20260113" in " ".join(completed.stderr.split())
