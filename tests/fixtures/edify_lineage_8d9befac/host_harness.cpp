// Host-only synthetic evaluator for the pinned *reference* Lineage edify.
// There is deliberately no implementation that opens a partition or writes to
// the filesystem. Every installer-specific callback below is a mock.
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "edify/expr.h"

static std::vector<std::string> writes;
static std::string failure_partition;
static std::string failure_kind;
static bool completed = false;
static bool wrong_device = false;

static std::vector<std::string> strings(State* state,
                                        const std::vector<std::unique_ptr<Expr>>& argv) {
  std::vector<std::string> values;
  if (!ReadArgs(state, argv, &values)) throw std::runtime_error("mock argument failed");
  return values;
}

static Value* get_property(const char*, State* state,
                           const std::vector<std::unique_ptr<Expr>>& argv) {
  auto args = strings(state, argv);
  if (args.size() != 1 || (args[0] != "ro.product.device" && args[0] != "ro.build.product"))
    throw std::runtime_error("unexpected mock property");
  return StringValue(wrong_device ? "not-joyeuse" : "joyeuse");
}

static Value* no_write_extract(const char*, State* state,
                               const std::vector<std::unique_ptr<Expr>>& argv) {
  auto args = strings(state, argv);
  const std::vector<std::string> ordered = {"super", "boot", "dtbo"};
  if (args.size() != 2 || writes.size() >= ordered.size())
    throw std::runtime_error("unexpected mock extract count or arguments");
  const std::string& part = ordered[writes.size()];
  if (args[0] != part + ".img" || args[1] != "/dev/block/bootdevice/by-name/" + part)
    throw std::runtime_error("unexpected mock partition or order");
  writes.push_back(part);  // A record in memory only: no device or file is opened.
  if (part == failure_partition) {
    if (failure_kind == "empty") return StringValue("");
    if (failure_kind == "null") return nullptr;
    throw std::runtime_error("unexpected synthetic failure kind");
  }
  return StringValue("t");
}

static Value* no_op(const char* name, State* state,
                    const std::vector<std::unique_ptr<Expr>>& argv) {
  auto args = strings(state, argv);
  if (std::string(name) == "ui_print") {
    for (const auto& arg : args) {
      if (arg.find("Flashing completed") != std::string::npos) completed = true;
    }
  }
  return StringValue("t");
}

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  failure_partition = argv[1];
  failure_kind = argv[2];
  wrong_device = (failure_partition == "wrong-device");
  if (!(failure_partition == "none" || failure_partition == "wrong-device" ||
        failure_partition == "super" || failure_partition == "boot" ||
        failure_partition == "dtbo")) return 2;
  if (!(failure_kind == "none" || failure_kind == "empty" || failure_kind == "null")) return 2;
  std::string script((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
  if (script.empty() || script.size() > 1024 * 1024 || script.find('\0') != std::string::npos)
    return 2;
  try {
    RegisterBuiltins();
    RegisterFunction("getprop", get_property);
    RegisterFunction("package_extract_file", no_write_extract);
    RegisterFunction("ui_print", no_op);
    RegisterFunction("show_progress", no_op);
    RegisterFunction("set_progress", no_op);
    std::unique_ptr<Expr> root;
    int errors = 0;
    if (ParseString(script, &root, &errors) != 0 || errors != 0 || !root) return 3;
    State state(script, nullptr);
    std::unique_ptr<Value> result(EvaluateValue(&state, root));
    std::cout << "parsed=1\n" << "aborted=" << (result ? 0 : 1) << '\n'
              << "completed=" << (completed ? 1 : 0) << '\n'
              << "error_present=" << (state.errmsg.empty() ? 0 : 1) << '\n'
              << "writes=";
    for (size_t i = 0; i < writes.size(); ++i) {
      if (i) std::cout << ',';
      std::cout << writes[i];
    }
    std::cout << '\n';
    return 0;
  } catch (const std::exception& exc) {
    std::cerr << "host harness refused: " << exc.what() << '\n';
    return 4;
  }
}
