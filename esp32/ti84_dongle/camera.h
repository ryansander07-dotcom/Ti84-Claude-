// The dongle's camera: small grayscale previews and full-size JPEG photos.
#pragma once

#include <stddef.h>
#include <stdint.h>

bool camera_begin();
bool camera_ok();

// Fill gray (PREVIEW_W * PREVIEW_H bytes) with a fresh preview frame.
bool camera_preview(uint8_t *gray);

// Take a full-size photo and keep it until the next one. Returns false on failure.
bool camera_snap();
bool camera_has_photo();
const uint8_t *camera_photo(size_t *len);
