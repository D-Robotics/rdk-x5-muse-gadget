# D-Robotics hand nodes

Source-only copies of the official Apache-2.0 TROS 2.4.1 hand nodes. No model
weights are included. The original algorithms are compiled directly into the
Muse vision runtime because the installed packages expose only executables.

- hand_lmk_detection: `455abc11fb79ebdc0fb2080edb6a1945a226fb23`
- hand_gesture_detection: `22c9600917ec50b5aa2f52c01299dcc2afaa50ea`

Upstream: https://github.com/D-Robotics/hand_lmk_detection and
https://github.com/D-Robotics/hand_gesture_detection.

main.cpp is omitted and original license headers are retained. The landmark
node time-conversion helper is made file-local to avoid a duplicate symbol.
CMake renames the landmark node timing helper at compile time to avoid a
duplicate global symbol when linking the two former executables together.
