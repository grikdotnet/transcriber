#pragma once

#include <string>
#include <vector>

namespace transcriber {
namespace infrastructure {

bool ApplyPinnedCmvn(const std::string& means_path, const std::string& istd_path,
                     std::vector<float>* features, int frame_count, int feature_dimension,
                     std::string* error);

}  // namespace infrastructure
}  // namespace transcriber
