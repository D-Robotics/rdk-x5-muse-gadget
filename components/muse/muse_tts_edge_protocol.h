/* Copyright (c) Meta Platforms, Inc. and affiliates.
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Pure protocol helpers, also exercised on the host. The two-byte length
 * belongs to Edge's application frame, not the WebSocket frame header. */
static inline size_t muse_tts_xml_escape(const char *src, char *dst, size_t cap)
{
    size_t n = 0;
    for (; *src; ++src) {
        unsigned char c = (unsigned char)*src;
        if (c < 32 && c != '\t' && c != '\n' && c != '\r') continue;
        const char *entity = NULL;
        switch (c) {
        case '&': entity = "&amp;"; break;
        case '<': entity = "&lt;"; break;
        case '>': entity = "&gt;"; break;
        case '\'': entity = "&apos;"; break;
        case '"': entity = "&quot;"; break;
        }
        size_t take = entity ? strlen(entity) : 1;
        if (n >= cap || take >= cap - n) return SIZE_MAX;
        if (entity) memcpy(dst + n, entity, take); else dst[n] = c;
        n += take;
    }
    if (n >= cap) return SIZE_MAX;
    dst[n] = 0;
    return n;
}

static inline uint64_t muse_tts_edge_ticks(uint64_t unix_seconds)
{
    uint64_t seconds = unix_seconds + UINT64_C(11644473600);
    return (seconds - seconds % 300) * UINT64_C(10000000);
}

static inline bool muse_tts_edge_path(const char *header, size_t len, const char *path)
{
    const size_t want = strlen(path);
    for (size_t off = 0; off < len;) {
        size_t end = off;
        while (end < len && header[end] != '\r' && header[end] != '\n') ++end;
        if (end == off) return false; /* End of headers; never inspect the body. */
        if (end - off == 5 + want && !memcmp(header + off, "Path:", 5) &&
            !memcmp(header + off + 5, path, want)) return true;
        off = end;
        if (off < len && header[off] == '\r') ++off;
        if (off < len && header[off] == '\n') ++off;
    }
    return false;
}

typedef struct {
    uint8_t prefix[2];
    size_t prefix_got, header_len, header_got;
    char header[1024];
    bool audio, failed;
} muse_tts_edge_frame_t;

static inline void muse_tts_edge_frame_reset(muse_tts_edge_frame_t *f)
{
    memset(f, 0, sizeof(*f));
}

static inline bool muse_tts_edge_frame_feed(muse_tts_edge_frame_t *f,
    const uint8_t *data, size_t len, uint8_t *audio, size_t cap, size_t *used)
{
    if (f->failed || *used > cap) return false;
    size_t off = 0;
    while (f->prefix_got < 2 && off < len) f->prefix[f->prefix_got++] = data[off++];
    if (f->prefix_got < 2) return true;
    if (!f->header_len) {
        f->header_len = ((size_t)f->prefix[0] << 8) | f->prefix[1];
        if (!f->header_len || f->header_len > sizeof(f->header)) {
            f->failed = true;
            return false;
        }
    }
    size_t take = f->header_len - f->header_got;
    if (take > len - off) take = len - off;
    memcpy(f->header + f->header_got, data + off, take);
    f->header_got += take;
    off += take;
    if (f->header_got < f->header_len) return true;
    f->audio = muse_tts_edge_path(f->header, f->header_len, "audio");
    if (!f->audio) return true;
    if (len - off > cap - *used) {
        f->failed = true;
        return false;
    }
    memcpy(audio + *used, data + off, len - off);
    *used += len - off;
    return true;
}
