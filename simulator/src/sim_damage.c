#include "sim_damage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "src/drivers/sdl/lv_sdl_window.h"

#ifdef MUSE_X11_DAMAGE
#include <SDL_syswm.h>
#include <X11/Xutil.h>
#include <stdatomic.h>

static struct {
    Display *connection;
    Window window;
    GC gc;
    XImage *image;
    uint16_t *shadow;
    unsigned long palette[65536];
    lv_display_t *display;
    lv_timer_t *timer;
    int width, height;
    atomic_bool expose;
} s_damage;

static unsigned long channel(unsigned value, unsigned long mask)
{
    unsigned shift = 0;
    if (!mask) return 0;
    while (!(mask & 1)) { mask >>= 1; ++shift; }
    return ((value * mask + 127) / 255) << shift;
}

static void damage_flush(lv_display_t *display, const lv_area_t *area, uint8_t *pixels)
{
    int x1 = s_damage.width, y1 = s_damage.height, x2 = -1, y2 = -1;
    bool expose = atomic_exchange(&s_damage.expose, false);
    int ax1 = expose ? 0 : area->x1, ay1 = expose ? 0 : area->y1;
    int ax2 = expose ? s_damage.width - 1 : area->x2;
    int ay2 = expose ? s_damage.height - 1 : area->y2;
    const uint16_t *source = (const uint16_t *)pixels;
    for (int y = ay1; y <= ay2; ++y) {
        for (int x = ax1; x <= ax2; ++x) {
            size_t index = (size_t)y * s_damage.width + x;
            uint16_t pixel = source[index];
            if (!expose && s_damage.shadow[index] == pixel) continue;
            s_damage.shadow[index] = pixel;
            XPutPixel(s_damage.image, x, y, s_damage.palette[pixel]);
            if (x < x1) x1 = x;
            if (y < y1) y1 = y;
            if (x > x2) x2 = x;
            if (y > y2) y2 = y;
        }
    }
    if (x2 >= x1 && y2 >= y1) {
        XPutImage(s_damage.connection, s_damage.window, s_damage.gc, s_damage.image,
                  x1, y1, x1, y1, x2 - x1 + 1, y2 - y1 + 1);
        /* Bound outstanding X requests instead of queuing old frames. */
        XSync(s_damage.connection, False);
    }
    lv_display_flush_ready(display);
}

static void repaint(lv_timer_t *timer)
{
    (void)timer;
    if (atomic_load(&s_damage.expose)) lv_obj_invalidate(lv_screen_active());
}

static void cleanup(lv_event_t *event)
{
    (void)event;
    if (s_damage.timer) lv_timer_delete(s_damage.timer);
    if (s_damage.image) XDestroyImage(s_damage.image);
    if (s_damage.gc) XFreeGC(s_damage.connection, s_damage.gc);
    if (s_damage.connection) XCloseDisplay(s_damage.connection);
    free(s_damage.shadow);
    memset(&s_damage, 0, sizeof(s_damage));
}
#endif

bool sim_damage_start(lv_display_t *display)
{
#ifdef MUSE_X11_DAMAGE
    const char *enabled = getenv("MUSE_UI_X11_DAMAGE");
    if (enabled && !strcmp(enabled, "0")) return false;
    SDL_SysWMinfo info;
    SDL_VERSION(&info.version);
    SDL_Window *window = lv_sdl_window_get_window(display);
    if (!SDL_GetWindowWMInfo(window, &info) || info.subsystem != SDL_SYSWM_X11 ||
        lv_display_get_color_format(display) != LV_COLOR_FORMAT_RGB565) {
        fprintf(stderr, "[display] damage unavailable: SDL=%s format=%d error=%s\n",
                SDL_GetCurrentVideoDriver(), (int)lv_display_get_color_format(display), SDL_GetError());
        return false;
    }
    s_damage.connection = XOpenDisplay(NULL);
    s_damage.window = info.info.x11.window;
    XWindowAttributes attributes;
    if (!s_damage.connection || !XGetWindowAttributes(s_damage.connection, s_damage.window, &attributes)) {
        cleanup(NULL);
        return false;
    }
    s_damage.width = lv_display_get_horizontal_resolution(display);
    s_damage.height = lv_display_get_vertical_resolution(display);
    if (attributes.width != s_damage.width || attributes.height != s_damage.height ||
        (attributes.visual->class != TrueColor && attributes.visual->class != DirectColor)) {
        fprintf(stderr, "[display] damage unavailable: window=%dx%d target=%dx%d visual=%d\n",
                attributes.width, attributes.height, s_damage.width, s_damage.height,
                attributes.visual->class);
        cleanup(NULL);
        return false;
    }
    s_damage.image = XCreateImage(s_damage.connection, attributes.visual, attributes.depth,
        ZPixmap, 0, NULL, s_damage.width, s_damage.height, 32, 0);
    s_damage.shadow = calloc((size_t)s_damage.width * s_damage.height, sizeof(uint16_t));
    if (s_damage.image) s_damage.image->data = calloc(s_damage.height, s_damage.image->bytes_per_line);
    s_damage.gc = XCreateGC(s_damage.connection, s_damage.window, 0, NULL);
    if (!s_damage.image || !s_damage.image->data || !s_damage.shadow || !s_damage.gc) {
        cleanup(NULL);
        return false;
    }
    for (unsigned p = 0; p < 65536; ++p)
        s_damage.palette[p] = channel(((p >> 11) & 31) * 255 / 31, attributes.visual->red_mask) |
                              channel(((p >> 5) & 63) * 255 / 63, attributes.visual->green_mask) |
                              channel((p & 31) * 255 / 31, attributes.visual->blue_mask);
    s_damage.display = display;
    atomic_store(&s_damage.expose, true);
    s_damage.timer = lv_timer_create(repaint, 10, NULL);
    lv_display_set_flush_cb(display, damage_flush);
    lv_display_add_event_cb(display, cleanup, LV_EVENT_DELETE, NULL);
    fprintf(stderr, "[display] X11 changed-region updates enabled\n");
    return true;
#else
    (void)display;
    return false;
#endif
}

void sim_damage_event(const SDL_Event *event)
{
#ifdef MUSE_X11_DAMAGE
    if (s_damage.connection && event->type == SDL_WINDOWEVENT &&
        (event->window.event == SDL_WINDOWEVENT_EXPOSED ||
         event->window.event == SDL_WINDOWEVENT_TAKE_FOCUS))
        atomic_store(&s_damage.expose, true);
#else
    (void)event;
#endif
}

bool sim_damage_read_rgb(uint8_t *pixels, int width, int height)
{
#ifdef MUSE_X11_DAMAGE
    if (!s_damage.connection || width != s_damage.width || height != s_damage.height) return false;
    for (int i = 0; i < width * height; ++i) {
        uint16_t p = s_damage.shadow[i];
        pixels[i * 3] = ((p >> 11) & 31) * 255 / 31;
        pixels[i * 3 + 1] = ((p >> 5) & 63) * 255 / 63;
        pixels[i * 3 + 2] = (p & 31) * 255 / 31;
    }
    return true;
#else
    (void)pixels; (void)width; (void)height;
    return false;
#endif
}
