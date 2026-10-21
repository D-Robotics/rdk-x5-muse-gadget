# RDK X5 native Muse UI

This adapted LVGL/SDL host runner renders the Muse pixel avatar and captions in a 480×320 native desktop window. It is used as the real display frontend on X5; it does not emulate ESP32 hardware. See the root README for deployment.

```sh
cmake -S simulator -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

`/run/muse-ui/state` carries UTF-8 UI state from the backend. Touch events go to `/run/muse-ui/input.sock`. The Desktop button and Esc close the frontend.

The UI targets 30 FPS (`MUSE_UI_FPS`, 1–30). Linux X11 builds with `libx11-dev`
update changed pixel regions instead of presenting the whole window. This
keeps animation within the SPI link's bandwidth. Set `MUSE_UI_X11_DAMAGE=0`
to use the original SDL renderer. Other platforms and headless tests use SDL.
`MUSE_UI_FPS_METRICS=1` logs software render FPS every five seconds; it does
not measure the panel's electrical refresh rate. Model and video rates are
configured separately in `/etc/default/muse-pet-vision`.

The included headless scenarios verify the renderer, not networking, audio hardware or an XFCE session.
