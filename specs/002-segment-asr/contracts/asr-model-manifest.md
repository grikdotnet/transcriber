# ASR Model Manifest Contract

ASR Model Manifests are versioned, closed JSON documents shipped as application resources. Their
presence means a model is supported; it does not mean the model artifacts are installed.

The normative structural contract is
[asr-model-manifest.schema.json](asr-model-manifest.schema.json). The first-party decoder adds these
semantic checks that JSON Schema cannot express concisely:

1. The manifest filename without `.json` equals `id`.
2. `artifacts.root` and every artifact `path` are relative and contain no empty, `.` or `..` path
   component.
3. No two artifact roles resolve to the same path.
4. All resolved artifact files remain beneath the application model root.
5. `source_url` uses HTTPS and is metadata only; ASR never contacts it.
6. Unknown root, capability, artifact, and artifact-record fields are rejected.

## Initial built-in manifest

```json
{
  "schema_version": 1,
  "id": "qwen3-asr-1.7b",
  "display_name": "Qwen3-ASR 1.7B Q8_0",
  "source_url": "https://huggingface.co/ggml-org/Qwen3-ASR-1.7B-GGUF",
  "execution_provider": "llama-cpp",
  "capabilities": {
    "context": true,
    "language": "optional"
  },
  "artifacts": {
    "root": "qwen3-asr-1.7b",
    "files": {
      "model": {
        "path": "Qwen3-ASR-1.7B-Q8_0.gguf",
        "sha256": "58e22d0532d4eacaf034cfac17a6fed159f37c41390c710186783be439d1fc57"
      },
      "audio_projector": {
        "path": "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf",
        "sha256": "46c1d533af3f354ceb37ce855dbceff7da7fa7cf1e6a523df3b13440bd164c0d"
      }
    }
  }
}
```

Language support is not enumerated in this document. `optional` means the model permits automatic
language handling or an explicit language request. `required` means an explicit language request is
mandatory. Model-to-language matching is a separate capability.

Artifact checksums support the separate installer/downloader boundary. `transcriber-asr` validates
artifact existence but does not hash model files on every invocation.
