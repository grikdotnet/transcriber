# Execution Provider contract

## Request and completion

The existing per-segment request retains audio path, recognition context, requested language, and timeout. The bundled Qwen/llama.cpp adapter sends one nonstreaming chat request with `logprobs:true` and `top_logprobs:1`. A result is complete only when exactly one assistant choice has `finish_reason:"stop"`. Missing or abnormal terminal information fails the ASR Task.

## Ordered result

The adapter exposes an ordered sequence of transcript Recognition Tokens (`token_id`, authoritative Unicode `text`, `log_probability`). The adapter removes only provider-defined metadata, controls, and stop markers. Literal text resembling markup is retained unless the provider contract defines it as control data. An item with no transcript text after control removal contributes no probability. A provider item containing both control and transcript text retains the transcript substring with the original ID and log probability. Empty transcript token text is ignored.

Qwen `language English<asr_text>I'm trying` becomes transcript tokens for `I'm trying`; the initial prefix and its token probabilities do not enter transcript scoring. Only the initial Qwen prefix is control metadata. Any later `language VALUE<asr_text>` sequence is literal transcript text. A Qwen phrase containing English and Russian may have one initial marker, which is discarded. `language None<asr_text>` is handled the same way; with no following text, the segment is empty. The Recognition Result has no language event or value.

The initial Qwen prefix may cross token boundaries. `VALUE` is non-empty and contains no line break; `None` is valid. An initial `<asr_text>` without `language VALUE`, or `language <asr_text>` with an empty value, is malformed metadata. Without a complete initial prefix, language-looking text is literal transcript text. Once transcript text begins, any later marker is literal.

## Validation

Each transcript token needs its original non-null provider-native ID (an integer in bundled llama.cpp), Unicode token string, and real non-boolean log probability ≤ 0; negative infinity is valid. Positive, NaN, missing, or malformed required values within a present transcript token fail at the provider-response boundary. An explicitly successful response with no `logprobs.content` field or an empty array means zero exposed tokens and a successful empty Speech Segment; a present non-array field fails. The adapter constructs transcript text and scores from the exposed Unicode token strings after defined control removal. The adapter neither reconstructs text from raw `bytes` or final assistant content nor compares token strings with final assistant content. llama.cpp stop handling may make those representations diverge; this is an accepted limitation rather than a response failure. Abnormal completion still prevents Transcript publication.

This contract replaces only the provider result shape in `specs/002-segment-asr/contracts/execution-provider.md`; lifecycle, deadlines, request context and requested-language behavior remain as specified there.
