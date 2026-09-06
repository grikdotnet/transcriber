#include "infrastructure/ncnn_inference.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "net.h"

namespace transcriber { namespace infrastructure {
namespace {

std::size_t LogicalElementCount(const ncnn::Mat& value) {
  if (value.dims == 1) return static_cast<std::size_t>(value.w) * value.elempack;
  if (value.dims == 2) {
    return static_cast<std::size_t>(value.w) * value.h * value.elempack;
  }
  if (value.dims == 3) {
    return static_cast<std::size_t>(value.w) * value.h * value.c * value.elempack;
  }
  if (value.dims == 4) {
    return static_cast<std::size_t>(value.w) * value.h * value.d * value.c * value.elempack;
  }
  return 0;
}

}  // namespace

InferenceStatus RunNcnn(const std::string& model_param, const std::string& model_bin,
                        const std::vector<float>& features, int frame_count,
                        int chunk_max_frames, std::vector<float>* probabilities,
                        std::string* error) {
  ncnn::Net network;
  if (network.load_param(model_param.c_str()) != 0 ||
      network.load_model(model_bin.c_str()) != 0) {
    *error = "asset loading failed for NCNN model";
    return InferenceStatus::kAssetFailure;
  }
  probabilities->clear();
  probabilities->reserve(static_cast<std::size_t>(frame_count));
  const int chunk_count = (frame_count + chunk_max_frames - 1) / chunk_max_frames;
  const int balanced_chunk_size = (frame_count + chunk_count - 1) / chunk_count;
  for (int offset = 0; offset < frame_count; offset += balanced_chunk_size) {
    const int count = std::min(balanced_chunk_size, frame_count - offset);
    ncnn::Mat input(80, count);
    std::memcpy(input.data, features.data() + static_cast<std::size_t>(offset) * 80U,
                static_cast<std::size_t>(count) * 80U * sizeof(float));
    ncnn::Extractor extractor = network.create_extractor();
    if (extractor.input("in0", input) != 0) {
      *error = "NCNN input binding failed";
      return InferenceStatus::kInferenceFailure;
    }
    ncnn::Mat result;
    if (extractor.extract("out0", result) != 0 ||
        LogicalElementCount(result) != static_cast<std::size_t>(count)) {
      *error = "NCNN inference output count mismatch";
      return InferenceStatus::kInferenceFailure;
    }
    for (int index = 0; index < count; ++index) {
      const float probability = result[index];
      if (!std::isfinite(probability) || probability < 0.0F || probability > 1.0F) {
        *error = "NCNN inference produced an invalid probability";
        return InferenceStatus::kInferenceFailure;
      }
      probabilities->push_back(probability);
    }
  }
  return InferenceStatus::kOk;
}

}  // namespace infrastructure
}  // namespace transcriber
