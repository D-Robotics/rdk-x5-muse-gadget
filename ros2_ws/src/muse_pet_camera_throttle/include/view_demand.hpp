#pragma once
#include <cstdlib>
#include <ctime>
#include <sys/stat.h>

namespace muse {
inline bool depth_requested(const char *path, std::time_t now) {
  struct stat lease;
  return !stat(path, &lease) && now >= lease.st_mtime && now - lease.st_mtime < 3;
}
inline bool depth_requested() {
  const char *path = std::getenv("MUSE_PET_DEPTH_LEASE");
  return depth_requested(path ? path : "/run/user/1000/muse-depth.active", std::time(nullptr));
}
}
