# RDK X5 native Muse UI

This adapted LVGL/SDL host runner renders the Muse pixel avatar and captions in a 480×320 native desktop window. It is used as the real display frontend on X5; it does not emulate ESP32 hardware. See the root README for deployment.

```sh
cmake -S simulator -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

`/run/muse-ui/state` carries UTF-8 UI state from the backend. Touch events go to `/run/muse-ui/input.sock`. The Desktop button and Esc close the frontend. LVGL and animation refresh are limited to 8 fps for the SPI screen.

The included headless scenarios verify the renderer, not networking, audio hardware or an XFCE session.
