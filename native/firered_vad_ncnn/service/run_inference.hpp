#pragma once

#include <string>

#include "protocol/runner_command.hpp"

namespace transcriber {
namespace service {

struct RunResult {
  int status;
  std::string output;
  std::string error;
};

RunResult RunInference(const protocol::RunnerCommand& command);

}  // namespace service
}  // namespace transcriber
