#pragma once

#include <string>
#include <vector>

namespace transcriber { namespace infrastructure {

struct FrontendOutput {
  int total_samples;
  int frame_count;
  std::vector<float> features;
};

enum class FrontendStatus { kOk, kAudioFailure, kAssetFailure, kProcessingFailure };

FrontendStatus RunPinnedFrontend(const std::string& audio_path,
                                 const std::string& means_path,
                                 const std::string& istd_path,
                                 FrontendOutput* output,
                                 std::string* error);

}  // namespace infrastructure
}  // namespace transcriber
