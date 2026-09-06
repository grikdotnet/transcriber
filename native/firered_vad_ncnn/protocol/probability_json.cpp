#include "protocol/probability_json.hpp"

#include <iomanip>
#include <limits>
#include <sstream>

namespace transcriber { namespace protocol {

std::string EncodeProbabilityDocument(int total_samples,
                                      const std::vector<float>& probabilities) {
  std::ostringstream output;
  output << "{\"schema_version\":1,\"audio\":{\"sample_rate_hz\":16000,"
            "\"channels\":1,\"sample_format\":\"pcm_s16le\",\"total_samples\":"
         << total_samples
         << "},\"frames\":{\"frame_length_samples\":400,"
            "\"frame_shift_samples\":160,\"frame_count\":"
         << probabilities.size() << ",\"probabilities\":[";
  output << std::setprecision(std::numeric_limits<float>::max_digits10);
  for (std::size_t index = 0; index < probabilities.size(); ++index) {
    if (index != 0) output << ',';
    output << probabilities[index];
  }
  output << "]}}\n";
  return output.str();
}

}  // namespace protocol
}  // namespace transcriber
