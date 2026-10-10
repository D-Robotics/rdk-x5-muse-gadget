/* Copyright (c) Meta Platforms, Inc. and affiliates.
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once
#include <stdint.h>
#include <stddef.h>

/* Called by the Muse chat task, or an idle bench test. Requests run on a separate worker so
 * chat events and cancellation keep flowing during HTTPS/WSS synthesis.
 * poll: 0 pending, 1 complete (caller frees *audio), -1 failed/cancelled. */
uint32_t muse_tts_edge_request(const char *text);
int muse_tts_edge_poll(uint32_t ticket, uint8_t **audio, size_t *len);
void muse_tts_edge_cancel(void);
