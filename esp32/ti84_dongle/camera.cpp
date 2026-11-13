#include "camera.h"

#include <Arduino.h>
#include <esp_camera.h>
#include <img_converters.h>

#include <cstring>

#include "config.h"

namespace {

bool ready = false;
uint8_t *photo = nullptr;  // in PSRAM
size_t photo_len = 0;
uint8_t *rgb = nullptr;    // decoded preview, 2x PREVIEW size, BGR888
framesize_t current = FRAMESIZE_INVALID;

void use_size(framesize_t size) {
    if (size == current) return;
    sensor_t *s = esp_camera_sensor_get();
    s->set_framesize(s, size);
    current = size;
    // The first frames after a size change are often stale or half-exposed.
    for (int i = 0; i < 2; i++) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb) esp_camera_fb_return(fb);
    }
}

}  // namespace

bool camera_begin() {
    camera_config_t config = {};
    config.pin_pwdn = CAM_PIN_PWDN;
    config.pin_reset = CAM_PIN_RESET;
    config.pin_xclk = CAM_PIN_XCLK;
    config.pin_sccb_sda = CAM_PIN_SIOD;
    config.pin_sccb_scl = CAM_PIN_SIOC;
    config.pin_d7 = CAM_PIN_D7;
    config.pin_d6 = CAM_PIN_D6;
    config.pin_d5 = CAM_PIN_D5;
    config.pin_d4 = CAM_PIN_D4;
    config.pin_d3 = CAM_PIN_D3;
    config.pin_d2 = CAM_PIN_D2;
    config.pin_d1 = CAM_PIN_D1;
    config.pin_d0 = CAM_PIN_D0;
    config.pin_vsync = CAM_PIN_VSYNC;
    config.pin_href = CAM_PIN_HREF;
    config.pin_pclk = CAM_PIN_PCLK;
    config.xclk_freq_hz = 20000000;
    config.ledc_timer = LEDC_TIMER_0;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_UXGA;  // the largest size used, so buffers fit it
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;

    if (esp_camera_init(&config) != ESP_OK) return false;
    sensor_t *s = esp_camera_sensor_get();
    s->set_vflip(s, CAMERA_VFLIP);
    s->set_hmirror(s, CAMERA_HMIRROR);
    current = FRAMESIZE_UXGA;

    rgb = static_cast<uint8_t *>(ps_malloc(PREVIEW_W * 2 * PREVIEW_H * 2 * 3));
    ready = rgb != nullptr;
    if (ready) use_size(FRAMESIZE_QVGA);
    return ready;
}

bool camera_ok() { return ready; }

bool camera_preview(uint8_t *gray) {
    if (!ready) return false;
    use_size(FRAMESIZE_QVGA);  // 320x240, averaged down to 160x120
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return false;
    bool ok = fb->width == PREVIEW_W * 2 && fb->height == PREVIEW_H * 2 &&
              fmt2rgb888(fb->buf, fb->len, fb->format, rgb);
    esp_camera_fb_return(fb);
    if (!ok) return false;

    const int src_w = PREVIEW_W * 2;
    for (int y = 0; y < PREVIEW_H; y++) {
        for (int x = 0; x < PREVIEW_W; x++) {
            int sum = 0;
            for (int dy = 0; dy < 2; dy++) {
                const uint8_t *p = rgb + ((y * 2 + dy) * src_w + x * 2) * 3;
                // Channel order doesn't matter: blue and red get equal weight.
                sum += p[0] + 2 * p[1] + p[2] + p[3] + 2 * p[4] + p[5];
            }
            gray[y * PREVIEW_W + x] = static_cast<uint8_t>(sum / 16);
        }
    }
    return true;
}

bool camera_snap() {
    if (!ready) return false;
    use_size(FRAMESIZE_UXGA);  // 1600x1200, close to what Claude reads best
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return false;
    free(photo);
    photo = static_cast<uint8_t *>(ps_malloc(fb->len));
    if (photo) {
        memcpy(photo, fb->buf, fb->len);
        photo_len = fb->len;
    } else {
        photo_len = 0;
    }
    esp_camera_fb_return(fb);
    use_size(FRAMESIZE_QVGA);
    return photo != nullptr;
}

bool camera_has_photo() { return photo != nullptr; }

const uint8_t *camera_photo(size_t *len) {
    *len = photo_len;
    return photo;
}
