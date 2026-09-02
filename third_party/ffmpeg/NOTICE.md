# FFmpeg distribution notice

This application bundles an unmodified FFmpeg command-line executable.

- FFmpeg project: https://ffmpeg.org/
- Binary provider: https://evermeet.cx/ffmpeg/
- Pinned release and checksums: `manifest.json`
- Build provenance: `build-config.txt`
- License: GPL-3.0-or-later for the selected prebuilt artifacts

The generated executable is stored at `vendor/ffmpeg` and is intentionally
excluded from Git. Run `scripts/fetch-ffmpeg-macos.sh` to reproduce it.

Evermeet publishes an Intel x86_64 executable. This project intentionally uses
that executable on both Intel and Apple Silicon Macs.

Release packaging must retain this notice, include the complete applicable
license texts, and make the corresponding source code available.
