#pragma once

#include <string>
#include <vector>

namespace transcriber { namespace infrastructure {

enum class InferenceStatus { kOk, kAssetFailure, kInferenceFailure };

InferenceStatus RunNcnn(const std::string& model_param, const std::string& model_bin,
                        const std::vector<float>& features, int frame_count,
                        int chunk_max_frames, std::vector<float>* probabilities,
                        std::string* error);

}  // namespace infrastructure
}  // namespace transcriber
