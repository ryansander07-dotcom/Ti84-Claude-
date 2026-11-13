// Finds which camera wiring an ESP32-S3 camera board uses. Upload it, open the
// serial port, and read the report it prints every few seconds.
//
// Tries the wirings used by common ESP32-S3 camera boards. A wrong wiring just
// fails to find the camera; it doesn't harm the board.
#include <Arduino.h>
#include <esp_camera.h>
#include <esp_chip_info.h>
#include <esp_flash.h>

struct PinMap {
    const char *name;
    int pwdn, reset, xclk, sda, scl, d7, d6, d5, d4, d3, d2, d1, d0, vsync, href, pclk;
};

static const PinMap MAPS[] = {
    {"XIAO ESP32S3 Sense", -1, -1, 10, 40, 39, 48, 11, 12, 14, 16, 18, 17, 15, 38, 47, 13},
    {"ESP32-S3-EYE / Freenove S3 CAM", -1, -1, 15, 4, 5, 16, 17, 18, 12, 10, 8, 9, 11, 6, 7, 13},
    {"LilyGO T-Camera S3", -1, 39, 38, 5, 4, 9, 10, 11, 13, 21, 48, 47, 14, 8, 18, 12},
};

static String results;

static void probe() {
    results = "";
    for (const PinMap &m : MAPS) {
        camera_config_t c = {};
        c.pin_pwdn = m.pwdn; c.pin_reset = m.reset; c.pin_xclk = m.xclk;
        c.pin_sccb_sda = m.sda; c.pin_sccb_scl = m.scl;
        c.pin_d7 = m.d7; c.pin_d6 = m.d6; c.pin_d5 = m.d5; c.pin_d4 = m.d4;
        c.pin_d3 = m.d3; c.pin_d2 = m.d2; c.pin_d1 = m.d1; c.pin_d0 = m.d0;
        c.pin_vsync = m.vsync; c.pin_href = m.href; c.pin_pclk = m.pclk;
        c.xclk_freq_hz = 20000000;
        c.ledc_timer = LEDC_TIMER_0; c.ledc_channel = LEDC_CHANNEL_0;
        c.pixel_format = PIXFORMAT_JPEG; c.frame_size = FRAMESIZE_QVGA;
        c.jpeg_quality = 12; c.fb_count = 1;
        c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
        c.grab_mode = CAMERA_GRAB_LATEST;

        esp_err_t err = esp_camera_init(&c);
        results += String("  ") + m.name + ": ";
        if (err != ESP_OK) {
            results += "no camera (error 0x" + String(err, HEX) + ")\n";
            continue;
        }
        sensor_t *s = esp_camera_sensor_get();
        results += "FOUND sensor PID 0x" + String(s->id.PID, HEX);
        camera_fb_t *fb = nullptr;
        for (int i = 0; i < 3 && !fb; i++) fb = esp_camera_fb_get();
        if (fb) {
            results += ", took a " + String(fb->width) + "x" + String(fb->height) + " picture (" + String(fb->len) + " bytes)";
            esp_camera_fb_return(fb);
        } else {
            results += ", but no picture came back";
        }
        results += "\n";
        esp_camera_deinit();
        delay(200);
    }
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    probe();
}

void loop() {
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t flash = 0;
    esp_flash_get_size(nullptr, &flash);
    Serial.println("=== camera probe ===");
    Serial.printf("chip: ESP32-S3 rev %d, %d cores\n", chip.revision, chip.cores);
    Serial.printf("flash: %u MB, PSRAM: %s (%u KB)\n", (unsigned)(flash >> 20), psramFound() ? "yes" : "no",
                  (unsigned)(ESP.getPsramSize() / 1024));
    Serial.print(results);
    Serial.println("====================");
    delay(4000);
}
