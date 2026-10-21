#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <SDL.h>
#include "lvgl.h"

/* X11 damage blits keep SPI desktops from resending unchanged window pixels.
 * Other SDL drivers retain the normal renderer, including headless tests. */
bool sim_damage_start(lv_display_t *display);
void sim_damage_event(const SDL_Event *event);
bool sim_damage_read_rgb(uint8_t *pixels, int width, int height);
