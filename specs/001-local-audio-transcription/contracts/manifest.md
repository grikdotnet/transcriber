# Segment Manifest Contract v1

The serialized shape is defined by [manifest.schema.json](manifest.schema.json). A manifest document is intrinsically valid when it passes that schema and the document rules below. A manifest is publishable only when Service also proves the artifact-correspondence rules.

## Intrinsic document rules

1. `segments[index].index` equals its zero-based array position.
2. `duration_samples == end_sample - start_sample` for every segment.
3. `0 <= start_sample < end_sample <= audio.total_samples`.
4. Segments are ordered by `start_sample` and do not overlap: each segment's `start_sample` is greater than or equal to the previous segment's `end_sample`.
5. Each path equals `segments/segment-NNNN.wav`, where the decimal number is the segment index padded to at least four digits.
6. Every path is relative, contains no `..`, and lexically resolves inside the task work directory without filesystem access.
7. An empty `segments` array is the only valid document representation of a no-speech result.

## Publication artifact-correspondence rules

Service must prove all of these through Infrastructure before publication:

1. Each segment path resolves inside the task work directory to exactly one readable mono, 16 kHz, signed 16-bit PCM WAV whose frame count equals `duration_samples`.
2. No generated segment WAV is absent from the manifest, and no manifest segment lacks its file.
3. An empty `segments` array corresponds to no generated segment WAV files.

## Codec responsibilities

The Protocol manifest codec must:

- Validate the schema and all intrinsic document rules before producing JSON bytes.
- Decode only closed schema-v1 documents and revalidate all intrinsic document rules.
- Serialize deterministic UTF-8 JSON with one trailing newline.
- Reject non-integer numeric fields, escaping paths, gaps in indexes, inconsistent durations, invalid ordering, overlap, or out-of-audio bounds.

Filesystem existence, directory inventory, and WAV-header checks for the publication artifact-correspondence rules occur in Service through Infrastructure metadata before `manifest.json` is atomically published. The Protocol codec itself performs no filesystem I/O.

## Publication lifecycle

1. Build and validate the manifest entity in memory after interval planning.
2. Write and verify each referenced segment WAV.
3. Revalidate manifest/file correspondence in Service.
4. Atomically publish the already-created JSON bytes as `manifest.json`.

No failed task may leave a published document that claims unavailable segments.
