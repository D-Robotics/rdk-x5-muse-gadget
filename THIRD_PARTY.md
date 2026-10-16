# Third-party code and assets

- Muse UI, avatar, simulator adapters and vendored Linux SDK: [Meta Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/74a5e2d), Apache-2.0. Original file notices are preserved. RDK adaptations modify the original UI/simulator; the Python bridge and launcher are community additions.
- GNU Unifont 16.0.04 CJK bitmap subset, by Roman Czyborra, Paul Hardy and contributors: SIL Open Font License 1.1, or GPL-2.0-or-later with the font embedding exception. Distributed here under OFL 1.1. See `components/muse/fonts/README.md` and `LICENSES/Unifont-COPYING.txt`.
- LVGL 9.5.0 (MIT), SDL2 (zlib): fetched at build time or provided by the system. See `simulator/THIRD_PARTY.md`.
- Python dependencies are installed separately; their respective licenses apply.

- SPI initialization generator and legacy overlay sources: Shukun Huang's
  [Cathay-Launch-UI, revision 623032d](https://github.com/shockley6668/Cathay-Launch-UI/tree/623032d56395b018387b8f262ac0693e2ca28e2d),
  carried over at the author's request. The display guide documents corrections
  to pin numbering and the derived Waveshare pogo profile. Kernel module binaries
  and Linux driver source are not redistributed here.
- Vendor hardware geometry embedded in the CAD: D-Robotics RDK X5 and GS130WI,
  and Waveshare 3.5inch RPi LCD (F). Vendor geometry/marks retain their respective
  ownership and are not relicensed by this repository's code license. See
  [hardware/enclosure/README.md](hardware/enclosure/README.md) for source links.
