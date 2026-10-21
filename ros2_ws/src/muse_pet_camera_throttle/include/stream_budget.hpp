#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace muse {
using Clock = std::chrono::steady_clock;

class RateGate {
public:
  explicit RateGate(double fps) {
    if (!std::isfinite(fps) || fps <= 0 || fps > 30)
      throw std::invalid_argument("fps must be in (0, 30]");
    period_ = std::chrono::nanoseconds(static_cast<int64_t>(1e9 / fps));
  }
  bool ready(Clock::time_point now) {
    if (now < next_) return false;
    if (now - next_ > period_) next_ = now;
    next_ += period_;
    return true;
  }
private:
  std::chrono::nanoseconds period_{};
  Clock::time_point next_{};
};

class PreviewLease {
public:
  void update(bool active, Clock::time_point now) { active_ = active; refreshed_ = now; }
  bool active(Clock::time_point now) const {
    return active_ && now >= refreshed_ && now - refreshed_ < std::chrono::seconds(3);
  }
private:
  bool active_ = false;
  Clock::time_point refreshed_{};
};

// HbmMsg1080P reserves 6.2 MB. Copy only active pixels into a borrowed buffer.
// This is one bounded relay copy, not sensor-to-BPU zero-copy.
template<typename Frame>
bool copy_active_frame(const Frame &source, Frame &destination) {
  if (!source.width || !source.height || !source.data_size ||
      source.data_size > source.data.size() || source.data_size > destination.data.size())
    return false;
  destination.index = source.index;
  destination.time_stamp = source.time_stamp;
  destination.width = source.width;
  destination.height = source.height;
  destination.step = source.step;
  destination.encoding = source.encoding;
  destination.data_size = source.data_size;
  std::copy_n(source.data.begin(), source.data_size, destination.data.begin());
  return true;
}
}  // namespace muse
