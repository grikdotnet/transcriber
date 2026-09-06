#include "service/run_inference.hpp"

#include <vector>

#include "infrastructure/firered_frontend_adapter.hpp"
#include "infrastructure/ncnn_inference.hpp"
#include "protocol/probability_json.hpp"

namespace transcriber {
namespace service {

RunResult RunInference(const protocol::RunnerCommand& command) {
  infrastructure::FrontendOutput frontend;
  std::string error;
  const auto frontend_status = infrastructure::RunPinnedFrontend(
      command.audio, command.cmvn_means, command.cmvn_istd, &frontend, &error);
  if (frontend_status == infrastructure::FrontendStatus::kAudioFailure) return {3, "", error};
  if (frontend_status == infrastructure::FrontendStatus::kAssetFailure) return {4, "", error};
  if (frontend_status != infrastructure::FrontendStatus::kOk) return {5, "", error};

  std::vector<float> probabilities;
  const auto inference_status = infrastructure::RunNcnn(
      command.model_param, command.model_bin, frontend.features, frontend.frame_count,
      command.chunk_max_frames, &probabilities, &error);
  if (inference_status == infrastructure::InferenceStatus::kAssetFailure) return {4, "", error};
  if (inference_status != infrastructure::InferenceStatus::kOk) return {5, "", error};
  if (probabilities.size() != static_cast<std::size_t>(frontend.frame_count)) {
    return {5, "", "NCNN inference output count mismatch"};
  }
  return {0, protocol::EncodeProbabilityDocument(frontend.total_samples, probabilities), ""};
}

}  // namespace service
}  // namespace transcriber
