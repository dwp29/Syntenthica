#pragma once
#include <cstdlib>
#include <string>
// Not needed for the tested expressions; fail closed if unexpectedly reached.
namespace android::base {
inline std::string Trim(const std::string&) { std::abort(); }
}
