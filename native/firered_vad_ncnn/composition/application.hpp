#pragma once

#include "protocol/runner_command.hpp"
#include "service/run_inference.hpp"

namespace transcriber {
namespace composition {

service::RunResult RunApplication(const protocol::RunnerCommand& command);

}  // namespace composition
}  // namespace transcriber
