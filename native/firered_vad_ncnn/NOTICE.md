# Native provider distribution notice

This notice covers the separately distributed `firered-vad-ncnn` executable.
It records the inputs to that distribution; it does not determine or change
the license of this repository or any first-party source file.

## Compiled third-party source

The executable compiles these unmodified files from FireRedVAD commit
`c30ec49e8cc69642b0ee65362eba11b9d11c6e54`:

- `third_party/firered-vad/runtime-common-frontend/fbank.h`
- `third_party/firered-vad/runtime-common-frontend/fft.cc`
- `third_party/firered-vad/runtime-common-frontend/fft.h`
- `third_party/firered-vad/runtime-common-frontend/wav.h`
- the CMVN loader and `apply_cmvn` implementation from
  `third_party/firered-vad/runtime-ncnn-example/test_vad_non_stream.cpp`

FireRedVAD originates at <https://github.com/FireRedTeam/FireRedVAD> and is
licensed under Apache-2.0. Its complete license, file hashes, revision, and
distribution notice are recorded in `third_party/firered-vad/LICENSE`,
`third_party/firered-vad/manifest.json`, and
`third_party/firered-vad/NOTICE.md`. The headers under this provider's
`frontend/` directory are first-party forwarding headers and are not copied
upstream source.

## Linked dependencies

The executable statically links NCNN tag `20260113`, revision
`e956fbf9bd97fe945df35d736747dc816f8b5f42`, supplied at build time through
`NCNN_ROOT`. Configuration verifies that installation's
`ncnnConfigVersion.cmake` reports `20260113` and links the exact installed
`lib/libncnn.a`; it performs no shared-library or name-based fallback. NCNN
originates at <https://github.com/Tencent/ncnn> and uses the BSD-3-Clause
license together with notices for components under other licenses.
Distributions of the executable must accompany
`third_party/ncnn/LICENSE.txt`; exact provenance and linkage are recorded in
`third_party/ncnn/manifest.json`.

CMake also links the host Threads package and, on non-Windows hosts, the system
math library. These are platform/toolchain libraries rather than copied or
vendored project dependencies; their origin and applicable terms are supplied
by the target operating system and toolchain distribution.
