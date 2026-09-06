#define main firered_vad_pinned_example_main_not_invoked
#include "../../../third_party/firered-vad/runtime-ncnn-example/test_vad_non_stream.cpp"
#undef main

#include "infrastructure/upstream_cmvn_adapter.hpp"

namespace transcriber {
namespace infrastructure {

bool ApplyPinnedCmvn(const std::string& means_path, const std::string& istd_path,
                     std::vector<float>* features, int frame_count, int feature_dimension,
                     std::string* error) {
  std::vector<float> means;
  std::vector<float> istd;
  if (!load_binary_vector(means_path.c_str(), means) ||
      !load_binary_vector(istd_path.c_str(), istd) ||
      means.size() < static_cast<std::size_t>(feature_dimension) ||
      istd.size() < static_cast<std::size_t>(feature_dimension)) {
    *error = "asset loading failed for CMVN";
    return false;
  }
  apply_cmvn(means, istd, *features, frame_count, feature_dimension);
  return true;
}

}  // namespace infrastructure
}  // namespace transcriber
