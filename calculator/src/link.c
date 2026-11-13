#include "link.h"

#include <srldrvce.h>
#include <string.h>
#include <ti/getcsc.h>
#include <time.h>
#include <usbdrvce.h>

static srl_device_t srl;
static bool has_srl = false;
static uint8_t srl_buf[2048];

static char rx[1100];
static size_t rx_len = 0;

static usb_error_t handle_usb_event(usb_event_t event, void *event_data, usb_callback_data_t *callback_data) {
    usb_error_t err = srl_UsbEventCallback(event, event_data, callback_data);
    if (err != USB_SUCCESS) return err;

    /* Calculator is the host (dongle on an OTG cable): reset new devices so
       they get enabled. */
    if (event == USB_DEVICE_CONNECTED_EVENT && !(usb_GetRole() & USB_ROLE_DEVICE)) {
        usb_ResetDevice((usb_device_t)event_data);
    }

    /* Open the serial port when the dongle is enabled (calculator is host) or
       when a computer configures the calculator (calculator is the device). */
    if (event == USB_HOST_CONFIGURE_EVENT ||
        (event == USB_DEVICE_ENABLED_EVENT && !(usb_GetRole() & USB_ROLE_DEVICE))) {
        if (has_srl) return USB_SUCCESS;
        usb_device_t device;
        if (event == USB_HOST_CONFIGURE_EVENT) {
            device = usb_FindDevice(NULL, NULL, USB_SKIP_HUBS);
            if (device == NULL) return USB_SUCCESS;
        } else {
            device = (usb_device_t)event_data;
        }
        if (srl_Open(&srl, device, srl_buf, sizeof srl_buf, SRL_INTERFACE_ANY, 115200) == SRL_SUCCESS) {
            has_srl = true;
            rx_len = 0;
        }
    }

    if (event == USB_DEVICE_DISCONNECTED_EVENT && has_srl && (usb_device_t)event_data == srl.dev) {
        srl_Close(&srl);
        has_srl = false;
        rx_len = 0;
    }
    return USB_SUCCESS;
}

bool link_begin(void) {
    const usb_standard_descriptors_t *desc = srl_GetCDCStandardDescriptors();
    return usb_Init(handle_usb_event, NULL, desc, USB_DEFAULT_INIT_FLAGS) == USB_SUCCESS;
}

void link_end(void) {
    if (has_srl) srl_Close(&srl);
    has_srl = false;
    usb_Cleanup();
}

void link_poll(void) { usb_HandleEvents(); }

bool link_ready(void) { return has_srl; }

static void fill(void) {
    if (!has_srl || rx_len >= sizeof rx) return;
    int n = srl_Read(&srl, rx + rx_len, sizeof rx - rx_len);
    if (n > 0) rx_len += (size_t)n;
}

static bool write_all(const void *data, size_t len) {
    const uint8_t *p = data;
    clock_t deadline = clock() + 5 * CLOCKS_PER_SEC;
    while (len > 0) {
        if (!has_srl) return false;
        int n = srl_Write(&srl, p, len);
        if (n < 0) return false;
        p += n;
        len -= (size_t)n;
        if (len > 0) {
            if (clock() > deadline) return false;
            usb_HandleEvents();
        }
    }
    return true;
}

bool link_send(const char *line) {
    link_poll();
    return write_all(line, strlen(line)) && write_all("\n", 1);
}

int link_read_line(char *buf, size_t size, uint32_t timeout_s, bool allow_cancel) {
    clock_t deadline = clock() + (clock_t)timeout_s * CLOCKS_PER_SEC;
    for (;;) {
        usb_HandleEvents();
        if (!has_srl) return LINK_UNPLUGGED;
        fill();
        char *nl = memchr(rx, '\n', rx_len);
        if (nl) {
            size_t len = (size_t)(nl - rx);
            size_t keep = len < size - 1 ? len : size - 1;
            memcpy(buf, rx, keep);
            buf[keep] = '\0';
            if (keep > 0 && buf[keep - 1] == '\r') buf[--keep] = '\0';
            rx_len -= len + 1;
            memmove(rx, nl + 1, rx_len);
            return (int)keep;
        }
        if (rx_len >= sizeof rx) rx_len = 0; /* runaway line: drop it */
        if (allow_cancel && os_GetCSC() == sk_Clear) return LINK_CANCELLED;
        if (clock() > deadline) return LINK_TIMEOUT;
    }
}

bool link_read_bytes(uint8_t *dst, size_t len, uint32_t timeout_s) {
    clock_t deadline = clock() + (clock_t)timeout_s * CLOCKS_PER_SEC;
    size_t take = rx_len < len ? rx_len : len;
    memcpy(dst, rx, take);
    rx_len -= take;
    memmove(rx, rx + take, rx_len);
    dst += take;
    len -= take;
    while (len > 0) {
        usb_HandleEvents();
        if (!has_srl) return false;
        int n = srl_Read(&srl, dst, len);
        if (n > 0) {
            dst += n;
            len -= (size_t)n;
        } else if (clock() > deadline) {
            return false;
        }
    }
    return true;
}

void link_skip_to_end(uint32_t timeout_s) {
    char line[64];
    for (;;) {
        int n = link_read_line(line, sizeof line, timeout_s, true);
        if (n < 0 || strcmp(line, "END") == 0) return;
    }
}
