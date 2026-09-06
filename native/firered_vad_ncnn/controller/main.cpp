#include <iostream>

#include "composition/application.hpp"
#include "protocol/runner_command.hpp"

int main(int argc, char** argv) {
  transcriber::protocol::RunnerCommand command;
  std::string error;
  if (!transcriber::protocol::ParseRunnerCommand(argc, argv, &command, &error)) {
    std::cerr << "invalid arguments: " << error << '\n';
    return 2;
  }
  const transcriber::service::RunResult result =
      transcriber::composition::RunApplication(command);
  if (result.status == 0) {
    std::cout << result.output;
  } else {
    std::cerr << result.error << '\n';
  }
  return result.status;
}
