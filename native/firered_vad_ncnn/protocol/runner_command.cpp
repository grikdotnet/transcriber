#include "protocol/runner_command.hpp"

#include <climits>
#include <cstdlib>
#include <map>
#include <set>

namespace transcriber { namespace protocol {
namespace {

bool IsAbsolute(const std::string& path) { return !path.empty() && path[0] == '/'; }

}  // namespace

bool ParseRunnerCommand(int argc, char** argv, RunnerCommand* command,
                        std::string* error) {
  if (argc != 13) {
    *error = "expected six named options";
    return false;
  }
  std::map<std::string, std::string> values;
  for (int index = 1; index < argc; index += 2) {
    const std::string option(argv[index]);
    if (option != "--audio" && option != "--model-param" && option != "--model-bin" &&
        option != "--cmvn-means" && option != "--cmvn-istd" &&
        option != "--chunk-max-frames") {
      *error = "unknown option: " + option;
      return false;
    }
    if (!values.emplace(option, argv[index + 1]).second) {
      *error = "duplicate option: " + option;
      return false;
    }
  }
  const char* path_options[] = {"--audio", "--model-param", "--model-bin",
                                "--cmvn-means", "--cmvn-istd"};
  for (const char* option : path_options) {
    const auto found = values.find(option);
    if (found == values.end() || !IsAbsolute(found->second)) {
      *error = std::string(option) + " must be an absolute path";
      return false;
    }
  }
  const auto chunk = values.find("--chunk-max-frames");
  if (chunk == values.end()) {
    *error = "--chunk-max-frames is required";
    return false;
  }
  char* end = nullptr;
  const long parsed = std::strtol(chunk->second.c_str(), &end, 10);
  if (end == chunk->second.c_str() || *end != '\0' || parsed <= 0 || parsed > INT_MAX) {
    *error = "--chunk-max-frames must be a positive integer";
    return false;
  }
  command->audio = values["--audio"];
  command->model_param = values["--model-param"];
  command->model_bin = values["--model-bin"];
  command->cmvn_means = values["--cmvn-means"];
  command->cmvn_istd = values["--cmvn-istd"];
  command->chunk_max_frames = static_cast<int>(parsed);
  return true;
}

}  // namespace protocol
}  // namespace transcriber
