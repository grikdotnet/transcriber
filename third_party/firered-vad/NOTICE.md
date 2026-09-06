# FireRedVAD upstream notice

All copied source in this directory originates from
[FireRedVAD](https://github.com/FireRedTeam/FireRedVAD) commit
`c30ec49e8cc69642b0ee65362eba11b9d11c6e54` and is licensed under
Apache-2.0. The complete upstream license is retained as `LICENSE`, and the
revision plus hashes of native inputs are recorded in `manifest.json`.

Copied source inventory:

- `runtime-common-frontend/{fbank.h,fft.cc,fft.h,wav.h}`
- `runtime-ncnn-example/test_vad_non_stream.cpp`
- `fireredvad/{__init__.py,vad.py}`
- `fireredvad/core/{__init__.py,constants.py,vad_postprocessor.py}`

The runtime-common frontend and selected CMVN routines from the NCNN example
are compiled into the separately distributed native provider. The Python files
are redistributed as pinned source and loaded by the middleware's adapter.
Source redistributions must retain `LICENSE` and this notice; native binary
distributions must include the Apache-2.0 license and this attribution notice.

The staged NCNN example supplies the unchanged upstream CMVN loader and
`apply_cmvn` implementation used by the native runner. The adjacent
`fireredvad/` Python files are also pinned upstream components;
their provenance is recorded by the integration tests for that adapter.

This third-party notice records upstream provenance and distribution terms. It
does not determine or change the license of the containing repository.
