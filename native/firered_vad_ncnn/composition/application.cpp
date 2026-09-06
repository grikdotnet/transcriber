#include "composition/application.hpp"

namespace transcriber {
namespace composition {

service::RunResult RunApplication(const protocol::RunnerCommand& command) {
  return service::RunInference(command);
}

}  // namespace composition
}  // namespace transcriber
