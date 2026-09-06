#pragma once

#include <string>

namespace transcriber { namespace protocol {

struct RunnerCommand {
  std::string audio;
  std::string model_param;
  std::string model_bin;
  std::string cmvn_means;
  std::string cmvn_istd;
  int chunk_max_frames = 0;
};

bool ParseRunnerCommand(int argc, char** argv, RunnerCommand* command,
                        std::string* error);

}  // namespace protocol
}  // namespace transcriber
