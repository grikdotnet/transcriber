"""Typed schema-v1 ASR Model Manifest wire decoder."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Literal, cast
from urllib.parse import urlsplit

type LanguageBehavior = Literal["optional", "required"]

_STABLE_ID: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
_ARTIFACT_ROLE: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*\Z")
_ARTIFACT_PATH: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_SHA256: Final[re.Pattern[str]] = re.compile(r"[a-f0-9]{64}\Z")
_HTTPS_URL: Final[re.Pattern[str]] = re.compile(r"https://\S+\Z")


@dataclass(frozen=True, slots=True)
class AsrModelCapabilities:
    """Capabilities declared by one ASR Model Manifest."""

    context: bool
    language: LanguageBehavior


@dataclass(frozen=True, slots=True)
class AsrModelArtifact:
    """One role-keyed relative model artifact requirement."""

    role: str
    path: PurePosixPath
    sha256: str


@dataclass(frozen=True, slots=True)
class AsrModelArtifacts:
    """Relative model artifact requirements in manifest declaration order."""

    root: PurePosixPath
    files: tuple[AsrModelArtifact, ...]


@dataclass(frozen=True, slots=True)
class AsrModelManifest:
    """A decoded built-in ASR Model Manifest independent of local artifact state."""

    schema_version: Literal[1]
    id: str
    display_name: str
    source_url: str
    execution_provider: str
    capabilities: AsrModelCapabilities
    artifacts: AsrModelArtifacts


def _require_object(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_exact_fields(
    document: dict[str, object], field_name: str, expected: tuple[str, ...]
) -> None:
    if set(document) != set(expected):
        raise ValueError(f"{field_name} fields must be exactly: {', '.join(expected)}")


def _require_string(value: object, field_name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _require_boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_stable_id(value: object, field_name: str) -> str:
    identifier = _require_string(value, field_name, nonempty=True)
    if _STABLE_ID.fullmatch(identifier) is None:
        raise ValueError(f"{field_name} must be a safe stable ID")
    return identifier


def _require_safe_relative_path(value: object, field_name: str) -> PurePosixPath:
    path_text = _require_string(value, field_name, nonempty=True)
    path = PurePosixPath(path_text)
    if (
        _ARTIFACT_PATH.fullmatch(path_text) is None
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path_text.split("/"))
    ):
        raise ValueError(f"{field_name} must be a safe relative path")
    return path


def _require_filename(filename: str | None, model_id: str) -> None:
    if filename is None:
        return
    if not isinstance(filename, str) or "/" in filename or "\\" in filename:
        raise ValueError("ASR Model Manifest filename must be a bare filename")
    if filename != f"{model_id}.json":
        raise ValueError("ASR Model Manifest filename must equal the model ID plus .json")


def decode_asr_model_manifest(
    payload: str | bytes, *, filename: str | None = None
) -> AsrModelManifest:
    """Decode a closed schema-v1 manifest without reading model artifact installation state."""

    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("ASR Model Manifest must be valid JSON") from error

    document = _require_object(decoded, "ASR Model Manifest")
    _require_exact_fields(
        document,
        "ASR Model Manifest",
        (
            "schema_version",
            "id",
            "display_name",
            "source_url",
            "execution_provider",
            "capabilities",
            "artifacts",
        ),
    )
    schema_version = document["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise ValueError("schema_version must be integer 1")
    model_id = _require_stable_id(document["id"], "id")
    display_name = _require_string(document["display_name"], "display_name", nonempty=True)
    source_url = _require_string(document["source_url"], "source_url", nonempty=True)
    if _HTTPS_URL.fullmatch(source_url) is None or not urlsplit(source_url).netloc:
        raise ValueError("source_url must be an HTTPS URL")
    execution_provider = _require_stable_id(document["execution_provider"], "execution_provider")

    capabilities_document = _require_object(document["capabilities"], "capabilities")
    _require_exact_fields(capabilities_document, "capabilities", ("context", "language"))
    language = _require_string(capabilities_document["language"], "capabilities.language")
    if language not in {"optional", "required"}:
        raise ValueError("capabilities.language must be optional or required")
    artifacts_document = _require_object(document["artifacts"], "artifacts")
    _require_exact_fields(artifacts_document, "artifacts", ("root", "files"))
    root_text = _require_stable_id(artifacts_document["root"], "artifacts.root")
    root = _require_safe_relative_path(root_text, "artifacts.root")
    files_document = _require_object(artifacts_document["files"], "artifacts.files")
    if not files_document:
        raise ValueError("artifacts.files must be non-empty")
    files: list[AsrModelArtifact] = []
    resolved_paths: set[PurePosixPath] = set()
    for role, record in files_document.items():
        if _ARTIFACT_ROLE.fullmatch(role) is None:
            raise ValueError("artifact role must be a safe identifier")
        artifact_document = _require_object(record, role)
        _require_exact_fields(artifact_document, role, ("path", "sha256"))
        path = _require_safe_relative_path(artifact_document["path"], f"{role}.path")
        resolved_path = root / path
        if resolved_path in resolved_paths:
            raise ValueError("duplicate artifact path")
        resolved_paths.add(resolved_path)
        sha256 = _require_string(artifact_document["sha256"], f"{role}.sha256")
        if _SHA256.fullmatch(sha256) is None:
            raise ValueError(f"{role}.sha256 must be a lowercase SHA-256 checksum")
        files.append(AsrModelArtifact(role=role, path=path, sha256=sha256))

    _require_filename(filename, model_id)
    return AsrModelManifest(
        schema_version=1,
        id=model_id,
        display_name=display_name,
        source_url=source_url,
        execution_provider=execution_provider,
        capabilities=AsrModelCapabilities(
            context=_require_boolean(capabilities_document["context"], "capabilities.context"),
            language=cast(LanguageBehavior, language),
        ),
        artifacts=AsrModelArtifacts(
            root=root,
            files=tuple(files),
        ),
    )
