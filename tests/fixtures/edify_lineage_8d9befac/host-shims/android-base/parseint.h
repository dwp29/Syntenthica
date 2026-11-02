#pragma once
#include <cstdlib>
#include <limits>
// The locked installer never exercises these helper functions. Abort if a
// future change unexpectedly reaches one instead of silently simulating it.
namespace android::base {
template <typename T>
bool ParseInt(const char*, T*, T = std::numeric_limits<T>::min(),
              T = std::numeric_limits<T>::max()) {
  std::abort();
}
}
