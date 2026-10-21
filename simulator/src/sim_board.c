/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "sim_board.h"
#include "sim_platform.h"
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include "sim_damage.h"

#include "src/drivers/sdl/lv_sdl_mouse.h"
#include "src/drivers/sdl/lv_sdl_window.h"

#define UI_WIDTH 480
#define UI_HEIGHT 320

static lv_display_t *s_display;

/* muse_ui.c reads the selected board through this production global. */
const muse_board_t *muse_board;

static void report_render_rate(lv_event_t *event)
{
    (void)event;
    static uint32_t started, frames;
    uint32_t now = SDL_GetTicks();
    if (!started) started = now;
    ++frames;
    if (now - started >= 5000) {
        fprintf(stderr, "[display] software render %.1f FPS (target period %d ms)\n",
                frames * 1000.0 / (now - started), muse_board->frame_ms);
        frames = 0;
        started = now;
    }
}

static esp_err_t sim_init(void)
{
    return ESP_OK;
}

static lv_display_t *sim_display_start(lv_indev_t **touch)
{
    s_display = lv_sdl_window_create(UI_WIDTH, UI_HEIGHT);
    if (!s_display) {
        return NULL;
    }
    /* The SDL driver installs SDL_GetTicks. Use the simulator clock instead so
     * scripted runs can advance time without sleeping and render repeatably. */
    lv_tick_set_cb(sim_time_tick_ms);
    lv_sdl_window_set_title(s_display, "Muse RDK X5");
    lv_sdl_window_set_resizeable(s_display, false);
    sim_damage_start(s_display);
    lv_timer_set_period(lv_display_get_refr_timer(s_display), muse_board->frame_ms);
    if (getenv("MUSE_UI_FPS_METRICS"))
        lv_display_add_event_cb(s_display, report_render_rate, LV_EVENT_RENDER_READY, NULL);
    if (touch) {
        *touch = lv_sdl_mouse_create();
    }
    return s_display;
}

static bool sim_display_lock(int timeout_ms)
{
    (void)timeout_ms;
    return true;
}

static void sim_display_unlock(void)
{
}

static void sim_set_brightness(int pct)
{
    (void)pct;
}

static void sim_panel_sleep(bool sleep)
{
    (void)sleep;
}

static esp_err_t sim_power_off(void)
{
    return ESP_FAIL;
}

static muse_board_t s_sim_board = {
    .name = "RDK X5 Display",
    .width = UI_WIDTH,
    .height = UI_HEIGHT,
    .round = false,
    .touch = true,
    .diagonal_in = 1.45f,
    .talk_button = "SPACE",
    .aux_button = "scroll",
    .talk_hint = { LV_ALIGN_CENTER, 100, -143 },
    .frame_ms = 33,
    .init = sim_init,
    .display_start = sim_display_start,
    .display_lock = sim_display_lock,
    .display_unlock = sim_display_unlock,
    .set_brightness = sim_set_brightness,
    .panel_sleep = sim_panel_sleep,
    .power_off = sim_power_off,
};

const muse_board_t *sim_board_get(void)
{
    const char *value = getenv("MUSE_UI_FPS");
    if (value && *value) {
        char *end;
        long fps = strtol(value, &end, 10);
        if (*end == '\0' && fps >= 1 && fps <= 30) {
            s_sim_board.frame_ms = (1000 + fps / 2) / fps;
        } else {
            fprintf(stderr, "MUSE_UI_FPS must be an integer from 1 to 30; using 30\n");
        }
    }
    return &s_sim_board;
}

lv_display_t *sim_board_display(void)
{
    return s_display;
}
