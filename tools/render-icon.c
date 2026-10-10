/* Render the existing Muse character for the Linux desktop launcher. */
#include <stdio.h>
#include "muse_pixel.h"

int main(void)
{
    uint16_t pixels[64 * 64];
    muse_pose_t pose = { .mode = MUSE_MODE_IDLE, .t = 1.0f, .mode_t = 1.0f };
    muse_pixel_set_size(64);
    muse_pixel_render(&pose);
    muse_pixel_scale(pixels, 64, 0, 63, 0, 63);
    printf("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"128\" height=\"128\" viewBox=\"0 0 80 80\">\n");
    printf("<title>Muse</title><rect width=\"80\" height=\"80\" rx=\"16\" fill=\"#171326\"/>\n");
    printf("<g transform=\"translate(8 8)\" shape-rendering=\"crispEdges\">\n");
    for (int y = 0; y < 64; y++) {
        for (int x = 0; x < 64;) {
            uint16_t color = pixels[y * 64 + x];
            int end = x + 1;
            while (end < 64 && pixels[y * 64 + end] == color) end++;
            if (color) {
                unsigned red = ((color >> 11) & 31) * 255 / 31;
                unsigned green = ((color >> 5) & 63) * 255 / 63;
                unsigned blue = (color & 31) * 255 / 31;
                printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"1\" fill=\"#%02x%02x%02x\"/>\n", x, y, end - x, red, green, blue);
            }
            x = end;
        }
    }
    puts("</g></svg>");
    return 0;
}
