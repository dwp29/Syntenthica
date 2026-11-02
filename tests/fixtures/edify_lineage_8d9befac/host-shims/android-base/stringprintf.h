#pragma once
#include <cstdarg>
#include <cstdlib>
#include <string>
// Not needed for the tested expressions; fail closed if unexpectedly reached.
namespace android::base {
inline void StringAppendV(std::string*, const char*, va_list) { std::abort(); }
}
