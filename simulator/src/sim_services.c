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

#include "sim_services.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "muse_console.h"
#include "muse_menu.h"
#include "muse_settings.h"
#include "muse_settings_ui.h"

#define SIM_DEFAULT_NAME "MuseGadget-SIM001"
#define SIM_DEFAULT_SSID "Muse Simulator"

static muse_wifi_status_t s_wifi = {
    .state = MUSE_WIFI_CONNECTED,
    .ssid = SIM_DEFAULT_SSID,
    .ip = "192.0.2.2",
    .rssi = -45,
};
static muse_ble_status_t s_ble = {
    .state = MUSE_BLE_CONNECTED,
    .secure = true,
    .name = SIM_DEFAULT_NAME,
};
static muse_hatch_status_t s_chat = {
    .state = MUSE_HATCH_REACHABLE,
};
static muse_link_state_t s_link = MUSE_LINK_ONLINE;
static int s_brightness = 75;
static bool s_speaker = true;
static bool s_audio_available;
static char s_pet_mode[24] = "idle";
static char s_pet_object[32] = "none";
static char s_pending_food[32];
static char s_pet_gesture[32] = "none";
static char s_pet_timer[32] = "off";
static char s_pet_app[40] = "none";
static char s_vision[40] = "waiting";
static char s_find_target[32];
static char s_find_state[24];
static int s_pet_hunger;
static int s_pet_happiness = 70;
static int s_pet_energy = 100;
static bool s_pet_active;
static lv_obj_t *s_pet_status_label;
static lv_obj_t *s_pet_stats_label;
static lv_obj_t *s_pet_detail_label;

void sim_services_set_audio(bool available)
{
    s_audio_available = available;
}

bool sim_services_audio_available(void)
{
    return s_audio_available;
}

static void copy_text(char *out, size_t cap, const char *text)
{
    if (!cap) {
        return;
    }
    if (!text) {
        text = "";
    }
    size_t n = strlen(text);
    if (n >= cap) {
        n = cap - 1;
    }
    memcpy(out, text, n);
    out[n] = '\0';
}

void sim_services_reset(void)
{
    s_wifi = (muse_wifi_status_t){
        .state = MUSE_WIFI_CONNECTED,
        .ssid = SIM_DEFAULT_SSID,
        .ip = "192.0.2.2",
        .rssi = -45,
    };
    s_ble = (muse_ble_status_t){
        .state = MUSE_BLE_CONNECTED,
        .secure = true,
        .name = SIM_DEFAULT_NAME,
    };
    s_chat = (muse_hatch_status_t){
        .state = MUSE_HATCH_REACHABLE,
    };
    s_link = MUSE_LINK_ONLINE;
    s_brightness = 75;
    s_speaker = true;
    copy_text(s_pet_mode, sizeof(s_pet_mode), "idle");
    copy_text(s_pet_object, sizeof(s_pet_object), "none");
    copy_text(s_pet_gesture, sizeof(s_pet_gesture), "none");
    copy_text(s_pet_timer, sizeof(s_pet_timer), "off");
    copy_text(s_pet_app, sizeof(s_pet_app), "none");
    copy_text(s_vision, sizeof(s_vision), "waiting");
    s_pet_hunger = 0;
    s_pet_happiness = 70;
    s_pet_energy = 100;
}

void sim_services_set_wifi(muse_wifi_state_t state, const char *ssid)
{
    s_wifi.state = state;
    copy_text(s_wifi.ssid, sizeof(s_wifi.ssid), ssid);
    copy_text(s_wifi.ip, sizeof(s_wifi.ip), state == MUSE_WIFI_CONNECTED ? "192.0.2.2" : "");
    s_wifi.rssi = state == MUSE_WIFI_CONNECTED ? -45 : 0;
    s_wifi.detail[0] = '\0';
}

void sim_services_set_ble(muse_ble_state_t state, const char *name, uint32_t passkey)
{
    s_ble.state = state;
    s_ble.passkey = passkey;
    s_ble.secure = state == MUSE_BLE_CONNECTED;
    copy_text(s_ble.name, sizeof(s_ble.name), name);
}

void sim_services_set_paired(bool paired)
{
    if (!paired) {
        s_chat.state = MUSE_HATCH_NOT_SET;
        s_chat.detail[0] = '\0';
    } else if (s_chat.state == MUSE_HATCH_NOT_SET) {
        s_chat.state = MUSE_HATCH_REACHABLE;
    }
}

void sim_services_set_chat_status(muse_hatch_state_t state, const char *detail)
{
    s_chat.state = state;
    copy_text(s_chat.detail, sizeof(s_chat.detail), detail);
}

void sim_services_set_link_state(muse_link_state_t state)
{
    s_link = state;
}

void sim_services_set_brightness(int pct)
{
    if (pct < 10) {
        pct = 10;
    } else if (pct > 100) {
        pct = 100;
    }
    s_brightness = pct;
}

void sim_services_set_speaker(bool on)
{
    s_speaker = on;
}

static bool set_pet_number(const char *value, int *out)
{
    char *end = NULL;
    long n = strtol(value, &end, 10);
    if (!value[0] || !end || *end || n < 0 || n > 100) {
        return false;
    }
    *out = (int)n;
    return true;
}

bool sim_services_set_pet_value(const char *key, const char *value)
{
    if (!strcmp(key, "pet_mode")) {
        s_pet_active = true;
        copy_text(s_pet_mode, sizeof(s_pet_mode), value);
    } else if (!strcmp(key, "pet_object")) {
        copy_text(s_pet_object, sizeof(s_pet_object), value);
    } else if (!strcmp(key, "pet_gesture")) {
        copy_text(s_pet_gesture, sizeof(s_pet_gesture), value);
    } else if (!strcmp(key, "pet_timer")) {
        copy_text(s_pet_timer, sizeof(s_pet_timer), value);
    } else if (!strcmp(key, "pet_app")) {
        copy_text(s_pet_app, sizeof(s_pet_app), value);
    } else if (!strcmp(key, "vision")) {
        copy_text(s_vision, sizeof(s_vision), value);
    } else if (!strcmp(key, "pet_hunger")) {
        return set_pet_number(value, &s_pet_hunger);
    } else if (!strcmp(key, "pet_happiness")) {
        return set_pet_number(value, &s_pet_happiness);
    } else if (!strcmp(key, "pet_energy")) {
        return set_pet_number(value, &s_pet_energy);
    } else if (!strcmp(key, "pet_find_target")) {
        copy_text(s_find_target, sizeof(s_find_target), value);
    } else if (!strcmp(key, "pet_find_state")) {
        copy_text(s_find_state, sizeof(s_find_state), value);
    } else if (!strcmp(key, "pet_pending_food")) {
        copy_text(s_pending_food, sizeof(s_pending_food), value);
    } else if (!strncmp(key, "pet_", 4)) {
        /* Detailed engine fields are available to petctl; the renderer only
         * needs the subset above. Keep the state protocol extensible. */
        return true;
    } else {
        return false;
    }
    return true;
}

const char *sim_services_pet_mode(void)
{
    return s_pet_mode;
}

bool sim_services_pet_active(void)
{
    return s_pet_active;
}

const char *sim_services_pet_badge(void)
{
    static char badge[80];
    badge[0] = '\0';
    if (strcmp(s_pet_timer, "off") && strcmp(s_pet_timer, "cancelled")) {
        snprintf(badge, sizeof(badge), "Focus %s", s_pet_timer);
    } else if (!strcmp(s_find_state, "searching") || !strcmp(s_find_state, "found")) {
        snprintf(badge, sizeof(badge), "%s %s",
                 !strcmp(s_find_state, "found") ? "Found" : "Find", s_find_target);
    } else if (!strcmp(s_pet_mode, "eating")) {
        snprintf(badge, sizeof(badge), "Yum!");
    } else if (!strcmp(s_pending_food, "banana")) {
        snprintf(badge, sizeof(badge), "Banana + OK");
    }
    return badge;
}

int muse_settings_brightness(void)
{
    return s_brightness;
}

bool muse_settings_speaker_on(void)
{
    return s_speaker;
}

void muse_settings_set_brightness(int pct)
{
    sim_services_set_brightness(pct);
}

extern void muse_backend_mute(void);

void muse_settings_set_speaker_on(bool on)
{
    sim_services_set_speaker(on);
    muse_backend_mute();
}

void muse_wifi_status(muse_wifi_status_t *out)
{
    if (out) {
        *out = s_wifi;
    }
}

bool muse_wifi_connected(void)
{
    return s_wifi.state == MUSE_WIFI_CONNECTED;
}

void muse_ble_status(muse_ble_status_t *out)
{
    if (out) {
        *out = s_ble;
    }
}

void muse_hatch_status(muse_hatch_status_t *out)
{
    if (out) {
        *out = s_chat;
    }
}

muse_link_state_t muse_link_state(void)
{
    return s_link;
}

extern void muse_backend_pet_action(const char *action);

static void on_pet_action(lv_event_t *event)
{
    const char *action = lv_event_get_user_data(event);
    if (action) {
        muse_backend_pet_action(action);
    }
}

static void add_pet_button(lv_obj_t *parent, const char *text, const char *action)
{
    lv_obj_t *button = lv_button_create(parent);
    lv_obj_set_size(button, 116, 44);
    lv_obj_set_style_bg_color(button, lv_color_hex(0x211d35), 0);
    lv_obj_set_style_radius(button, 14, 0);
    lv_obj_add_event_cb(button, on_pet_action, LV_EVENT_CLICKED, (void *)action);
    lv_obj_t *label = lv_label_create(button);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_label_set_text(label, text);
    lv_obj_center(label);
}

void muse_settings_ui_build(lv_obj_t *tile)
{
    lv_obj_set_style_bg_color(tile, lv_color_black(), 0);
    lv_obj_t *title = lv_label_create(tile);
    lv_label_set_text(title, "PET CONTROLS");
    lv_obj_set_style_text_color(title, lv_color_hex(0xa77dff), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 12);

    s_pet_status_label = lv_label_create(tile);
    lv_obj_set_style_text_color(s_pet_status_label, lv_color_white(), 0);
    lv_obj_set_style_text_font(s_pet_status_label, &lv_font_montserrat_16, 0);
    lv_obj_align(s_pet_status_label, LV_ALIGN_TOP_MID, 0, 44);

    s_pet_stats_label = lv_label_create(tile);
    lv_obj_set_style_text_color(s_pet_stats_label, lv_color_hex(0xd8d2ff), 0);
    lv_obj_align(s_pet_stats_label, LV_ALIGN_TOP_MID, 0, 69);

    lv_obj_t *buttons = lv_obj_create(tile);
    lv_obj_remove_style_all(buttons);
    lv_obj_set_size(buttons, 420, 106);
    lv_obj_align(buttons, LV_ALIGN_CENTER, 0, 13);
    lv_obj_set_flex_flow(buttons, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(buttons, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER,
                          LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(buttons, 10, 0);
    lv_obj_set_style_pad_row(buttons, 8, 0);
    add_pet_button(buttons, "Wake", "wake");
    add_pet_button(buttons, "Feed", "feed");
    add_pet_button(buttons, "Focus 25", "timer start 25");
    add_pet_button(buttons, "Find banana", "find banana");
    add_pet_button(buttons, "Sleep", "sleep");
    add_pet_button(buttons, "Stop timer", "timer cancel");

    s_pet_detail_label = lv_label_create(tile);
    lv_obj_set_width(s_pet_detail_label, 440);
    lv_obj_set_style_text_font(s_pet_detail_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_align(s_pet_detail_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(s_pet_detail_label, lv_color_hex(0x8b84a8), 0);
    lv_obj_align(s_pet_detail_label, LV_ALIGN_BOTTOM_MID, 0, -27);
}

void muse_settings_ui_tick(bool visible)
{
    if (!visible || !s_pet_status_label) {
        return;
    }
    char status[96];
    snprintf(status, sizeof(status), "%s  |  %s", s_pet_mode, s_pet_timer);
    lv_label_set_text(s_pet_status_label, status);
    char stats[96];
    snprintf(stats, sizeof(stats), "Hunger %d   Happy %d   Energy %d",
             s_pet_hunger, s_pet_happiness, s_pet_energy);
    lv_label_set_text(s_pet_stats_label, stats);
    char detail[192];
    snprintf(detail, sizeof(detail), "Vision: %s  |  Gesture: %s\nObject: %s  |  App: %s",
             s_vision, s_pet_gesture, s_pet_object, s_pet_app);
    lv_label_set_text(s_pet_detail_label, detail);
}

bool muse_settings_ui_in_subpage(void)
{
    return false;
}

void muse_menu_key(muse_menu_key_t key)
{
    (void)key;
}

bool muse_menu_is_open(void)
{
    return false;
}

void muse_menu_build(lv_obj_t *parent, int w, int h)
{
    (void)parent;
    (void)w;
    (void)h;
}

bool muse_menu_tick(float now)
{
    (void)now;
    return false;
}

void muse_menu_close(void)
{
}

void muse_console_write(const void *buf, size_t n)
{
    if (buf && n) {
        (void)fwrite(buf, 1, n, stdout);
        (void)fflush(stdout);
    }
}
