#include "infrastructure/firered_frontend_adapter.hpp"

#include <cstdint>
#include <cstdio>

#include "frontend/fbank.h"
#include "frontend/wav.h"
#include "infrastructure/upstream_cmvn_adapter.hpp"

namespace transcriber { namespace infrastructure {
namespace {

bool HasPcmFormatCode(const std::string& path) {
  FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) return false;
  std::uint8_t header[22] = {};
  const bool read = std::fread(header, 1, sizeof(header), file) == sizeof(header);
  std::fclose(file);
  return read && header[0] == 'R' && header[1] == 'I' && header[2] == 'F' &&
         header[3] == 'F' && header[8] == 'W' && header[9] == 'A' &&
         header[10] == 'V' && header[11] == 'E' && header[20] == 1 && header[21] == 0;
}

}  // namespace

FrontendStatus RunPinnedFrontend(const std::string& audio_path,
                                 const std::string& means_path,
                                 const std::string& istd_path,
                                 FrontendOutput* output,
                                 std::string* error) {
  if (!HasPcmFormatCode(audio_path)) {
    *error = "audio must use PCM format code 1";
    return FrontendStatus::kAudioFailure;
  }
  vad::WavReader reader;
  if (!reader.Open(audio_path)) {
    *error = "audio validation failed";
    return FrontendStatus::kAudioFailure;
  }
  if (reader.num_channel() != 1 || reader.sample_rate() != 16000 ||
      reader.bits_per_sample() != 16) {
    *error = "audio must be mono 16 kHz signed 16-bit PCM WAV";
    return FrontendStatus::kAudioFailure;
  }
  vad::Fbank frontend(80, 16000, 400, 160);
  output->frame_count = frontend.Compute(reader.GetMonoData(), &output->features);
  output->total_samples = reader.num_samples();
  if (output->frame_count <= 0 ||
      output->features.size() != static_cast<std::size_t>(output->frame_count) * 80U) {
    *error = "upstream preprocessing failed";
    return FrontendStatus::kProcessingFailure;
  }
  if (!ApplyPinnedCmvn(means_path, istd_path, &output->features, output->frame_count, 80,
                       error)) {
    return FrontendStatus::kAssetFailure;
  }
  return FrontendStatus::kOk;
}

}  // namespace infrastructure
}  // namespace transcriber
