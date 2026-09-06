#pragma once

#include <string>
#include <vector>

namespace transcriber { namespace protocol {

std::string EncodeProbabilityDocument(int total_samples,
                                      const std::vector<float>& probabilities);

}  // namespace protocol
}  // namespace transcriber
