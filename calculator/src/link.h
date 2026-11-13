/* USB serial link to the dongle (or to bridge.py on a computer). */
#ifndef LINK_H
#define LINK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define LINK_TIMEOUT (-1)
#define LINK_CANCELLED (-2)
#define LINK_UNPLUGGED (-3)

bool link_begin(void);
void link_end(void);
void link_poll(void);
bool link_ready(void);

/* Send one protocol line; the newline is added here. */
bool link_send(const char *line);

/* Read one line (without its newline) into buf. Returns its length, or one of
   the LINK_ codes. Pressing [clear] cancels when allow_cancel is true. */
int link_read_line(char *buf, size_t size, uint32_t timeout_s, bool allow_cancel);

/* Read exactly len raw bytes. */
bool link_read_bytes(uint8_t *dst, size_t len, uint32_t timeout_s);

/* Throw away input until an END line arrives (after a cancelled request).
   [clear] stops waiting. */
void link_skip_to_end(uint32_t timeout_s);

#endif
