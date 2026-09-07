# Execution Provider Contract

## Purpose

An Execution Provider adapter encapsulates runtime-specific process control, request transport,
response decoding, diagnostics, and cleanup. The ASR service does not know about HTTP, command-line
arguments, model tensors, or provider-specific control tokens.

## Application-facing lifecycle

```text
create(resolved_model, segment_root) -> fresh provider session
start(readiness_timeout=60s)
recognize(segment_index, audio_path, recognition_context, language, timeout=180s) -> text
stop(graceful_timeout=60s, force_timeout=10s)
```

Rules:

1. A session is fresh and stopped when created.
2. `start` is called at most once and must return only when the provider is ready for recognition.
3. `recognize` is valid only after successful `start` and before `stop`.
4. Calls are sequential and follow Segment Manifest order.
5. Successful text may be empty.
6. `stop` is idempotent and must reap the managed process. Graceful termination is bounded at 60
   seconds. If the process remains alive, `stop` must force termination and reap it within an
   additional 10 seconds.
7. Provider-originated errors carry a diagnostic excerpt separately from the application message so
   the controller can quote and escape it safely.
8. The adapter never publishes Transcript artifacts.

## Initial llama.cpp mapping

The `llama-cpp` registration resolves only `vendor/llama-server`; host `PATH` is not consulted.

Startup is equivalent to:

```text
vendor/llama-server
  --model <resolved model artifact>
  --mmproj <resolved audio_projector artifact>
  --host 127.0.0.1
  --port <ephemeral loopback port>
  --parallel 1
  --ctx-size 8192
  --media-path <validated task segments directory>
  --no-webui
```

The adapter polls `GET /health` until ready, process exit, cancellation, or the 60-second deadline.
Provider stdout/stderr is captured and drained without entering the public progress stream.

## Qwen recognition request

The adapter sends one non-streaming chat-completion request with deterministic sampling:

- system message: Recognition Context, or an empty string;
- user message: one `input_audio` item referencing the validated file within `--media-path`;
- optional assistant continuation: `language {ProviderLanguage}<asr_text>` when language is explicit;
- temperature: zero;
- request deadline: 180 seconds.

Common BCP 47 primary subtags are translated internally to Qwen's canonical language labels. This
translation is a provider wire concern and is not a public supported-language catalog or a model
selection mechanism.

## Qwen recognition response

The response must be valid JSON with exactly one usable assistant text value. The adapter accepts
Qwen's documented forms, including:

```text
language English<asr_text>Recognized words
```

It returns only `Recognized words`. `language None<asr_text>` with no following text returns an empty
successful result. Missing choices, missing/non-string content, invalid JSON, or unrecognized
structural shape is a `provider-response` failure.

HTTP errors use the provider JSON error message when available; process exits and startup failures
use the captured diagnostic tail. The controller owns final escaping, bounding, and rendering.
