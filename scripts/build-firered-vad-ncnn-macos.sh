#!/bin/sh
set -eu

if [ "${NCNN_ROOT:-}" = "" ]; then
  echo "NCNN_ROOT must point to the pinned NCNN 20260113 installation or build tree" >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
BUILD_DIR=${FIRERED_BUILD_DIR:-"$REPOSITORY_ROOT/build/firered-vad-ncnn"}
OUTPUT_PATH=${FIRERED_OUTPUT_PATH:-"$REPOSITORY_ROOT/vendor/firered-vad-ncnn"}

cmake -S "$REPOSITORY_ROOT/native/firered_vad_ncnn" -B "$BUILD_DIR" \
  -DNCNN_ROOT="$NCNN_ROOT" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --config Release --parallel
cmake -E make_directory "$(dirname -- "$OUTPUT_PATH")"
cmake -E copy "$BUILD_DIR/firered-vad-ncnn" "$OUTPUT_PATH"
chmod 755 "$OUTPUT_PATH"
