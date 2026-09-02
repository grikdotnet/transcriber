#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/.." && pwd)"
manifest="${FFMPEG_MANIFEST:-${repository_root}/third_party/ffmpeg/manifest.json}"
vendor_path="${FFMPEG_VENDOR_PATH:-${repository_root}/vendor/ffmpeg}"
operating_system="${FFMPEG_OS:-$(uname -s)}"
machine_architecture="${FFMPEG_ARCH:-$(uname -m)}"

if [[ "${operating_system}" != "Darwin" ]]; then
  printf 'This fetcher only supports macOS (Darwin), got %s.\n' "${operating_system}" >&2
  exit 1
fi

case "${machine_architecture}" in
  arm64 | aarch64 | x86_64 | amd64)
    ;;
  *)
    printf 'Unsupported macOS architecture: %s\n' "${machine_architecture}" >&2
    exit 1
    ;;
esac

for command_name in curl plutil shasum unzip; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "${command_name}" >&2
    exit 1
  fi
done

version="$(plutil -extract version raw -o - "${manifest}")"
url="$(plutil -extract artifact.url raw -o - "${manifest}")"
expected_archive_sha256="$(plutil -extract artifact.archiveSha256 raw -o - "${manifest}")"
binary_path="$(plutil -extract artifact.binaryPath raw -o - "${manifest}")"
expected_binary_sha256="$(plutil -extract artifact.binarySha256 raw -o - "${manifest}")"
downloaded_archive="$(mktemp -t transcriber-ffmpeg-archive.XXXXXX)"
extracted_binary="$(mktemp -t transcriber-ffmpeg-binary.XXXXXX)"
trap 'rm -f "${downloaded_archive}" "${extracted_binary}"' EXIT

printf 'Downloading FFmpeg %s for macOS x86_64...\n' "${version}"
curl --fail --location --retry 3 --silent --show-error --output "${downloaded_archive}" "${url}"

actual_archive_sha256="$(shasum -a 256 "${downloaded_archive}" | awk '{print $1}')"
if [[ "${actual_archive_sha256}" != "${expected_archive_sha256}" ]]; then
  printf 'FFmpeg archive checksum mismatch: expected %s, got %s.\n' \
    "${expected_archive_sha256}" "${actual_archive_sha256}" >&2
  exit 1
fi

unzip -p "${downloaded_archive}" "${binary_path}" >"${extracted_binary}"
actual_binary_sha256="$(shasum -a 256 "${extracted_binary}" | awk '{print $1}')"
if [[ "${actual_binary_sha256}" != "${expected_binary_sha256}" ]]; then
  printf 'FFmpeg binary checksum mismatch: expected %s, got %s.\n' \
    "${expected_binary_sha256}" "${actual_binary_sha256}" >&2
  exit 1
fi

chmod 0755 "${extracted_binary}"
"${extracted_binary}" -version >/dev/null

mkdir -p "$(dirname "${vendor_path}")"
install -m 0755 "${extracted_binary}" "${vendor_path}"

printf 'Installed FFmpeg %s at %s\n' "${version}" "${vendor_path}"
