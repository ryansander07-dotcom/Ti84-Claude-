// Settings for the dongle that are safe to commit. Your API key and Wi-Fi
// password go in secrets.h instead (copy secrets.example.h).
#pragma once

// Which board this is built for. The Meshnology W11 / XIAO (ESP32-S3) has the
// camera and a USB port the firmware drives itself. An ESP32-C3 board has no
// camera; its built-in USB serial port is the calculator link.
#if defined(CONFIG_IDF_TARGET_ESP32S3)
#define HAS_CAMERA 1
#define BOARD_NAME "ESP32-S3"
#define STATUS_LED_PIN -1  // the W11 has no LED of its own
#else
#define HAS_CAMERA 0
#define BOARD_NAME "ESP32-C3"
// The little blue LED on ESP32-C3 SuperMini-style boards. It lights when the
// pin is pulled low. The dongle turns it on as soon as it starts.
#define STATUS_LED_PIN 8
#define STATUS_LED_ON LOW
#endif

// Claude Opus 5.5 is the most accurate. "claude-haiku-5-5" is faster and
// much cheaper but makes more mistakes on hard problems.
#define CLAUDE_MODEL "claude-opus-5-5"
#define CLAUDE_EFFORT "medium"
#define CLAUDE_MAX_TOKENS 16000

// How long to wait for Claude before giving up, in milliseconds.
#define CLAUDE_TIMEOUT_MS 180000

// Longest message the dongle accepts from the calculator.
#define MAX_LINE 1024
#define MAX_QUESTION 500

// Preview frames sent to the calculator: 8-bit grayscale, shown at 2x.
#define PREVIEW_W 160
#define PREVIEW_H 120

// Set to 1 if the preview shows up upside down or mirrored.
#define CAMERA_VFLIP 0
#define CAMERA_HMIRROR 0

// How many Wi-Fi networks the dongle remembers. It joins the strongest one in
// range by itself whenever it isn't connected.
#define MAX_SAVED_NETWORKS 10

// Warn on the calculator when the estimated API credit drops below this many dollars.
#define CREDIT_LOW_USD 1.00

// Camera pins on the Seeed XIAO ESP32S3 Sense.
#define CAM_PIN_PWDN -1
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK 10
#define CAM_PIN_SIOD 40
#define CAM_PIN_SIOC 39
#define CAM_PIN_D7 48
#define CAM_PIN_D6 11
#define CAM_PIN_D5 12
#define CAM_PIN_D4 14
#define CAM_PIN_D3 16
#define CAM_PIN_D2 18
#define CAM_PIN_D1 17
#define CAM_PIN_D0 15
#define CAM_PIN_VSYNC 38
#define CAM_PIN_HREF 47
#define CAM_PIN_PCLK 13
