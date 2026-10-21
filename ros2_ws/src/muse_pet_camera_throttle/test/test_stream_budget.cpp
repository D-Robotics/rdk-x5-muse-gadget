#include "stream_budget.hpp"
#include "view_demand.hpp"
#include <unistd.h>
#include <utime.h>
#include <array>
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cstdint>
#include <limits>
#include <memory>

using namespace std::chrono_literals;
using muse::Clock;

struct Frame {
  int32_t index = 0;
  struct Stamp { int32_t sec = 0; uint32_t nanosec = 0; } time_stamp;
  uint32_t height = 0, width = 0, data_size = 0, step = 0;
  std::array<uint8_t, 12> encoding{};
  std::array<uint8_t, 6220800> data{};
};

int main() {
  char path[] = "/tmp/muse-view-XXXXXX";
  int fd = mkstemp(path); assert(fd >= 0); close(fd);
  struct utimbuf stamp{100,100}; assert(utime(path, &stamp) == 0);
  assert(muse::depth_requested(path, 100));
  assert(muse::depth_requested(path, 102));
  assert(!muse::depth_requested(path, 103));
  assert(!muse::depth_requested(path, 99));
  unlink(path); assert(!muse::depth_requested(path, 100));
  const Clock::time_point start{10s};
  muse::RateGate inference(10), preview(8);
  int inferred = 0, displayed = 0;
  for (int i = 0; i < 300; ++i) {
    const auto now = start + std::chrono::nanoseconds(i * int64_t{33333334});
    inferred += inference.ready(now);
    displayed += preview.ready(now);
  }
  assert(inferred == 100 && displayed == 80);
  const auto resumed = start + 30s;
  assert(inference.ready(resumed));
  assert(!inference.ready(resumed));  // No burst to repay a paused producer.
  for (double invalid : {0., -1., 31., std::numeric_limits<double>::quiet_NaN()}) {
    bool rejected = false;
    try { muse::RateGate gate(invalid); } catch (const std::invalid_argument &) { rejected = true; }
    assert(rejected);
  }
  muse::PreviewLease lease;
  assert(!lease.active(start));
  lease.update(true, start);
  assert(lease.active(start + 2999ms));
  assert(!lease.active(start + 3s));
  lease.update(true, start + 3s);
  assert(lease.active(start + 4s));
  lease.update(false, start + 4s);
  assert(!lease.active(start + 4s));

  // Use the real fixed-array capacity. Verify timestamps, active pixels and the
  // untouched tail, so an accidental full-message assignment is caught.
  auto source = std::make_unique<Frame>();
  auto target = std::make_unique<Frame>();
  source->index = 7;
  source->time_stamp.sec = 123;
  source->time_stamp.nanosec = 456;
  source->width = 960;
  source->height = 544;
  source->step = 960;
  source->data_size = 960 * 544 * 3 / 2;
  source->encoding[0] = 'n';
  source->data.fill(0x31);
  target->data.fill(0x72);
  assert(muse::copy_active_frame(*source, *target));
  assert(target->index == 7 && target->time_stamp.sec == 123 && target->time_stamp.nanosec == 456);
  assert(target->step == 960 && target->encoding[0] == 'n');
  assert(target->data_size == source->data_size);
  assert(target->data[source->data_size - 1] == 0x31);
  assert(target->data[source->data_size] == 0x72 && target->data.back() == 0x72);
  source->data_size = source->data.size() + 1;
  assert(!muse::copy_active_frame(*source, *target));
  source->data_size = 0;
  assert(!muse::copy_active_frame(*source, *target));
  source->data_size = 1;
  source->width = 0;
  assert(!muse::copy_active_frame(*source, *target));
}
