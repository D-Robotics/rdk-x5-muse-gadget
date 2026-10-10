# Third-party code and assets

- Muse UI, avatar, simulator adapters and vendored Linux SDK: [Meta Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/74a5e2d), Apache-2.0. Original file notices are preserved. RDK adaptations modify the original UI/simulator; the Python bridge and launcher are community additions.
- GNU Unifont 16.0.04 CJK bitmap subset, by Roman Czyborra, Paul Hardy and contributors: SIL Open Font License 1.1, or GPL-2.0-or-later with the font embedding exception. Distributed here under OFL 1.1. See `components/muse/fonts/README.md` and `LICENSES/Unifont-COPYING.txt`.
- LVGL 9.5.0 (MIT), SDL2 (zlib): fetched at build time or provided by the system. See `simulator/THIRD_PARTY.md`.
- Python dependencies are installed separately; their respective licenses apply.
