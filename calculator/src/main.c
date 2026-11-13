/* TI-84 Plus CE program for the Claude dongle.
 *
 * Menus: ask a question, photograph a problem with the dongle's camera,
 * join and manage Wi-Fi, see the API credit estimate, and check status. Talks the line protocol in the README over
 * USB, so it also works with bridge.py on a computer for testing.
 */
#include <graphx.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ti/getcsc.h>
#include <ti/screen.h>
#include <time.h>

#include "link.h"

#define COLS 26
#define ROWS 10
#define BODY_ROWS 9 /* rows 0-8; row 9 is the hint line */

#define MAX_LINES 300
#define MAX_INPUT 500
#define MAX_NETWORKS 20
#define NAME_LEN 32 /* longest Wi-Fi name */

#define PREVIEW_W 160
#define PREVIEW_H 120

/* Wait this long for Claude (it reads photos slowly) and for quick replies. */
#define SLOW_TIMEOUT 200
#define QUICK_TIMEOUT 10
#define PING_TIMEOUT 3
#define CANCEL_WAIT 30 /* after [clear], wait this long for the dongle to finish */

/* Room for a full Wi-Fi name; the screen shows the first COLS characters. */
static char lines[MAX_LINES][NAME_LEN + 1];
static int line_count;
static char line_kind[MAX_LINES]; /* 'A', 'E', 'S', 'N', 'W' or 'C' */

/* Last credit report from the dongle: cents left (-1 unknown) and
   0 ok, 1 low, 2 empty, 3 not set, -1 not asked yet. */
static long credit_cents = -1;
static int credit_code = -1;

static char input[MAX_INPUT + 1];
static char message[MAX_INPUT + 16];
static char reply[1100];

/* ---------- home screen text ---------- */

static void put_row(uint8_t row, const char *text) {
    char padded[COLS + 1];
    /* Never write the very last cell: that would scroll the home screen. */
    size_t width = row == ROWS - 1 ? COLS - 1 : COLS;
    size_t len = strlen(text);
    if (len > width) len = width;
    memset(padded, ' ', width);
    memcpy(padded, text, len);
    padded[width] = '\0';
    os_SetCursorPos(row, 0);
    os_PutStrLine(padded);
}

static void clear_screen(void) {
    for (uint8_t r = 0; r < ROWS; r++) put_row(r, "");
}

static void show_message(const char *title, const char *hint) {
    clear_screen();
    put_row(0, title);
    put_row(ROWS - 1, hint);
}

static void wait_for_key(void) {
    for (;;) {
        link_poll();
        uint8_t k = os_GetCSC();
        if (k == sk_Enter || k == sk_Clear) return;
    }
}

/* ---------- typing ---------- */

enum mode { MODE_MATH, MODE_LOWER, MODE_UPPER };

static const char *alpha_key(uint8_t k) {
    switch (k) {
        case sk_Math: return "a";   case sk_Apps: return "b";   case sk_Prgm: return "c";
        case sk_Recip: return "d";  case sk_Sin: return "e";    case sk_Cos: return "f";
        case sk_Tan: return "g";    case sk_Power: return "h";  case sk_Square: return "i";
        case sk_Comma: return "j";  case sk_LParen: return "k"; case sk_RParen: return "l";
        case sk_Div: return "m";    case sk_Log: return "n";    case sk_7: return "o";
        case sk_8: return "p";      case sk_9: return "q";      case sk_Mul: return "r";
        case sk_Ln: return "s";     case sk_4: return "t";      case sk_5: return "u";
        case sk_6: return "v";      case sk_Sub: return "w";    case sk_Store: return "x";
        case sk_1: return "y";      case sk_2: return "z";      case sk_0: return " ";
        case sk_DecPnt: return ":"; case sk_Chs: return "?";    case sk_Add: return "\"";
        case sk_3: return "'";
        default: return NULL;
    }
}

static const char *math_key(uint8_t k) {
    switch (k) {
        case sk_0: return "0"; case sk_1: return "1"; case sk_2: return "2"; case sk_3: return "3";
        case sk_4: return "4"; case sk_5: return "5"; case sk_6: return "6"; case sk_7: return "7";
        case sk_8: return "8"; case sk_9: return "9";
        case sk_DecPnt: return ".";  case sk_Chs: return "-";     case sk_Add: return "+";
        case sk_Sub: return "-";     case sk_Mul: return "*";     case sk_Div: return "/";
        case sk_Power: return "^";   case sk_LParen: return "(";  case sk_RParen: return ")";
        case sk_Comma: return ",";   case sk_GraphVar: return "x"; case sk_Square: return "^2";
        case sk_Store: return "=";   case sk_Sin: return "sin(";  case sk_Cos: return "cos(";
        case sk_Tan: return "tan(";  case sk_Log: return "log(";  case sk_Ln: return "ln(";
        case sk_Recip: return "^-1";
        default: return NULL;
    }
}

static const char *second_key(uint8_t k) {
    switch (k) {
        case sk_Square: return "sqrt("; case sk_Power: return "pi";  case sk_Ln: return "e^(";
        case sk_Log: return "10^(";     case sk_DecPnt: return "i";  case sk_Sin: return "asin(";
        case sk_Cos: return "acos(";    case sk_Tan: return "atan("; case sk_Div: return "e";
        case sk_0: return " ";          case sk_Math: return "<";    case sk_Apps: return ">";
        case sk_Store: return "!";      case sk_Comma: return "|";   case sk_Mul: return "[";
        case sk_Sub: return "]";        case sk_LParen: return "{";  case sk_RParen: return "}";
        default: return NULL;
    }
}

static void draw_input(const char *prompt, enum mode mode, bool second) {
    put_row(0, prompt);
    /* Show the tail of the text across rows 1-8, with a cursor. */
    char shown[(BODY_ROWS - 1) * COLS + 2];
    size_t len = strlen(input);
    size_t room = sizeof shown - 2;
    const char *start = len > room ? input + (len - room) : input;
    snprintf(shown, sizeof shown, "%s_", start);
    size_t shown_len = strlen(shown);
    for (uint8_t r = 0; r < BODY_ROWS - 1; r++) {
        char row[COLS + 1] = "";
        size_t off = (size_t)r * COLS;
        if (off < shown_len) {
            strncpy(row, shown + off, COLS);
            row[COLS] = '\0';
        }
        put_row(r + 1, row);
    }
    const char *mode_name = second ? "2nd" : mode == MODE_MATH ? "123" : mode == MODE_LOWER ? "abc" : "ABC";
    char hint[COLS];
    snprintf(hint, sizeof hint, "[%s] alpha=mode enter=ok", mode_name);
    put_row(ROWS - 1, hint);
}

/* Type text into `input`. Returns false if the user backs out with [clear]
   on an empty line. */
static bool get_text(const char *prompt, enum mode mode, size_t max_len) {
    bool second = false;
    input[0] = '\0';
    clear_screen();
    draw_input(prompt, mode, second);
    for (;;) {
        link_poll();
        uint8_t k = os_GetCSC();
        if (!k) continue;
        size_t len = strlen(input);
        if (k == sk_Enter) {
            if (len > 0) return true;
        } else if (k == sk_Clear) {
            if (len == 0) return false;
            input[0] = '\0';
        } else if (k == sk_Del || (k == sk_Left && !second)) {
            if (len > 0) input[len - 1] = '\0';
        } else if (k == sk_Alpha) {
            mode = mode == MODE_MATH ? MODE_LOWER : mode == MODE_LOWER ? MODE_UPPER : MODE_MATH;
            second = false;
        } else if (k == sk_2nd) {
            second = !second;
        } else {
            const char *add = second ? second_key(k) : mode == MODE_MATH ? math_key(k) : alpha_key(k);
            char upper[2];
            if (add && mode == MODE_UPPER && !second && add[0] >= 'a' && add[0] <= 'z') {
                upper[0] = (char)(add[0] - 'a' + 'A');
                upper[1] = '\0';
                add = upper;
            }
            if (add && len + strlen(add) <= max_len) strcat(input, add);
            second = false;
        }
        draw_input(prompt, mode, second);
    }
}

/* ---------- talking to the dongle ---------- */

/* Check something is answering on USB: send PING and wait briefly for PONG.
   Anything else that arrives first (the end of a cancelled answer) is thrown away. */
static bool ping(void) {
    if (!link_send("PING")) return false;
    for (;;) {
        int n = link_read_line(reply, sizeof reply, PING_TIMEOUT, true);
        if (n < 0) return false;
        if (strcmp(reply, "PONG") == 0) return true;
    }
}

static bool require_link(void) {
    for (int i = 0; i < 50 && !link_ready(); i++) {
        clock_t t = clock() + CLOCKS_PER_SEC / 50;
        while (clock() < t) link_poll();
    }
    if (!link_ready()) {
        show_message("Dongle not connected.", "enter: back");
        put_row(2, "Plug it into the USB port");
        put_row(3, "with the OTG cable, wait a");
        put_row(4, "few seconds, then try");
        put_row(5, "again.");
        wait_for_key();
        return false;
    }
    show_message("Checking the dongle...", "clear: cancel");
    if (ping()) return true;
    show_message("Nothing answered on USB.", "enter: back");
    put_row(2, "Plugged into a computer?");
    put_row(3, "Start bridge.py there.");
    put_row(5, "Dongle: if you just");
    put_row(6, "cancelled, it may still be");
    put_row(7, "finishing. Try again soon.");
    wait_for_key();
    return false;
}

/* Send a request and collect its reply lines until END. Returns false if the
   user cancelled or the link failed (an explanation is already in `lines`).
   With waiting == NULL nothing is drawn (for quick background checks). */
static bool request(const char *msg, const char *waiting, uint32_t timeout_s) {
    line_count = 0;
    if (waiting ? !require_link() : !link_ready()) return false;
    if (waiting) show_message(waiting, "clear: cancel");
    if (!link_send(msg)) {
        strcpy(lines[0], "Couldn't send. Is the");
        strcpy(lines[1], "dongle plugged in?");
        line_kind[0] = line_kind[1] = 'E';
        line_count = 2;
        return false;
    }

    clock_t started = clock();
    int dots = 0;
    for (;;) {
        int n = link_read_line(reply, sizeof reply, 1, true);
        if (n == LINK_TIMEOUT) {
            if ((uint32_t)((clock() - started) / CLOCKS_PER_SEC) >= timeout_s) {
                strcpy(lines[0], "No reply from the dongle.");
                line_kind[0] = 'E';
                line_count = 1;
                return false;
            }
            if (waiting) {
                char row[COLS + 1];
                dots = (dots + 1) % 4;
                snprintf(row, sizeof row, "%.*s", dots + 1, "....");
                put_row(1, row);
            }
            continue;
        }
        if (n == LINK_CANCELLED) {
            show_message("Cancelling...", "clear: stop waiting");
            link_skip_to_end(CANCEL_WAIT);
            line_count = 0;
            return false;
        }
        if (n == LINK_UNPLUGGED) {
            strcpy(lines[0], "Dongle was unplugged.");
            line_kind[0] = 'E';
            line_count = 1;
            return false;
        }
        if (strcmp(reply, "END") == 0) return true;
        if (n >= 2 && reply[0] == 'K' && reply[1] == ':') {
            /* K:<cents>,<state>: the credit estimate, not shown as a line */
            long cents;
            int code;
            if (sscanf(reply + 2, "%ld,%d", &cents, &code) == 2) {
                credit_cents = cents;
                credit_code = code;
            }
            continue;
        }
        if (n >= 2 && reply[1] == ':' && line_count < MAX_LINES) {
            line_kind[line_count] = reply[0];
            strncpy(lines[line_count], reply + 2, NAME_LEN);
            lines[line_count][NAME_LEN] = '\0';
            line_count++;
        }
    }
}

/* Scrollable view of `lines`. */
static void show_lines(void) {
    if (line_count == 0) return;
    int top = 0;
    int max_top = line_count > BODY_ROWS ? line_count - BODY_ROWS : 0;
    for (;;) {
        for (uint8_t r = 0; r < BODY_ROWS; r++) {
            int i = top + r;
            put_row(r, i < line_count ? lines[i] : "");
        }
        char hint[COLS];
        if (max_top > 0)
            snprintf(hint, sizeof hint, "%d-%d/%d arrows clr=back", top + 1,
                     top + BODY_ROWS < line_count ? top + BODY_ROWS : line_count, line_count);
        else
            snprintf(hint, sizeof hint, "clear: back");
        put_row(ROWS - 1, hint);

        uint8_t k;
        do {
            link_poll();
            k = os_GetCSC();
        } while (!k);
        if (k == sk_Clear || k == sk_Enter) return;
        if (k == sk_Down && top < max_top) top++;
        if (k == sk_Up && top > 0) top--;
        if (k == sk_Right) top = top + BODY_ROWS < max_top ? top + BODY_ROWS : max_top;
        if (k == sk_Left) top = top > BODY_ROWS ? top - BODY_ROWS : 0;
    }
}

/* ---------- menus ---------- */

static void ask_question(void) {
    if (!get_text("Ask Claude:", MODE_LOWER, MAX_INPUT)) return;
    snprintf(message, sizeof message, "Q:%s", input);
    request(message, "Asking Claude...", SLOW_TIMEOUT);
    show_lines();
}

/* Gray palette so preview bytes (0-255 brightness) can be drawn directly. */
static void gray_palette(void) {
    for (int i = 0; i < 256; i++) gfx_palette[i] = gfx_RGBTo1555(i, i, i);
    gfx_SetTextFGColor(255);
    gfx_SetTextBGColor(0);
    gfx_SetTextTransparentColor(1);
}

static void bar(const char *text) {
    gfx_SetColor(0);
    gfx_FillRectangle_NoClip(0, 228, GFX_LCD_WIDTH, 12);
    gfx_PrintStringXY(text, 2, 230);
}

/* Ask for one preview frame and draw it. */
static bool draw_preview(gfx_sprite_t *frame) {
    if (!link_send("VIEW")) return false;
    int n = link_read_line(reply, sizeof reply, QUICK_TIMEOUT, false);
    if (n < 0) return false;
    unsigned w, h, size;
    if (sscanf(reply, "F:%u,%u,%u", &w, &h, &size) != 3 || w != PREVIEW_W || h != PREVIEW_H ||
        size != PREVIEW_W * PREVIEW_H) {
        link_skip_to_end(QUICK_TIMEOUT);
        return false;
    }
    if (!link_read_bytes(frame->data, size, QUICK_TIMEOUT)) return false;
    link_skip_to_end(QUICK_TIMEOUT);
    gfx_ScaledSprite_NoClip(frame, 0, 0, 2, 2);
    return true;
}

enum photo_choice { PHOTO_CANCEL, PHOTO_SOLVE, PHOTO_NOTE };

/* Live preview until [enter] takes the picture; then confirm. */
static enum photo_choice aim_and_snap(gfx_sprite_t *frame) {
    for (;;) {
        bool snapped = false;
        while (!snapped) {
            link_poll();
            uint8_t k = os_GetCSC();
            if (k == sk_Clear) return PHOTO_CANCEL;
            if (k == sk_Enter) {
                bar("Taking the picture...");
                gfx_SwapDraw();
                link_send("SNAP");
                snapped = true;
                break;
            }
            if (draw_preview(frame)) {
                bar("ENTER: take picture   CLEAR: back");
            } else {
                gfx_FillScreen(0);
                bar("No camera picture. CLEAR: back");
            }
            gfx_SwapDraw();
            if (!link_ready()) return PHOTO_CANCEL;
        }

        bool ok = false;
        for (;;) {
            int n = link_read_line(reply, sizeof reply, 20, false);
            if (n < 0) break;
            if (strcmp(reply, "END") == 0) break;
            if (reply[0] == 'S') ok = true;
        }
        gfx_ScaledSprite_NoClip(frame, 0, 0, 2, 2);
        bar(ok ? "ENTER solve  Y= note  CLEAR retake" : "Didn't work. CLEAR: try again");
        gfx_SwapDraw();
        for (;;) {
            link_poll();
            uint8_t k = os_GetCSC();
            if (k == sk_Clear) break;
            if (ok && k == sk_Enter) return PHOTO_SOLVE;
            if (ok && k == sk_Yequ) return PHOTO_NOTE;
        }
    }
}

static void photo(void) {
    if (!require_link()) return;
    gfx_sprite_t *frame = gfx_MallocSprite(PREVIEW_W, PREVIEW_H);
    if (!frame) return;
    memset(frame->data, 0, PREVIEW_W * PREVIEW_H);

    gfx_Begin();
    gray_palette();
    gfx_SetDrawBuffer();
    enum photo_choice choice = aim_and_snap(frame);
    gfx_End();
    free(frame);
    clear_screen();

    if (choice == PHOTO_CANCEL) return;
    if (choice == PHOTO_NOTE) {
        if (!get_text("Note for Claude:", MODE_LOWER, MAX_INPUT)) return;
        snprintf(message, sizeof message, "PHOTO:%s", input);
    } else {
        strcpy(message, "PHOTO");
    }
    request(message, "Claude is reading it...", SLOW_TIMEOUT);
    show_lines();
}

/* ---------- Wi-Fi ---------- */

static char saved_names[MAX_NETWORKS][NAME_LEN + 1];
static int saved_count;
static char current_net[NAME_LEN + 1];

/* Ask the dongle which networks it remembers and which one it's on. */
static void load_saved(void) {
    saved_count = 0;
    current_net[0] = '\0';
    if (!request("SAVED", NULL, PING_TIMEOUT)) return;
    for (int i = 0; i < line_count; i++) {
        if (line_kind[i] == 'C') strcpy(current_net, lines[i]);
        if (line_kind[i] == 'W' && saved_count < MAX_NETWORKS) strcpy(saved_names[saved_count++], lines[i]);
    }
}

static bool is_saved(const char *name) {
    for (int i = 0; i < saved_count; i++)
        if (strcmp(saved_names[i], name) == 0) return true;
    return false;
}

/* A scrolling list. Returns the chosen index, or -1 for [clear]. The key that
   chose it ([enter] or [del]) goes in *key. `mark` puts a star before items. */
static int pick(const char *title, char items[][NAME_LEN + 1], int count, const char *hint,
                bool (*mark)(const char *), uint8_t *key) {
    int sel = 0, top = 0;
    for (;;) {
        clear_screen();
        put_row(0, title);
        for (uint8_t r = 0; r < BODY_ROWS - 1; r++) {
            int i = top + r;
            char row[COLS + 1] = "";
            if (i < count)
                snprintf(row, sizeof row, "%c%c%s", i == sel ? '>' : ' ', mark && mark(items[i]) ? '*' : ' ', items[i]);
            put_row(r + 1, row);
        }
        put_row(ROWS - 1, hint);
        uint8_t k;
        do {
            link_poll();
            k = os_GetCSC();
        } while (!k);
        if (k == sk_Clear) return -1;
        if (k == sk_Down && sel < count - 1) sel++;
        if (k == sk_Up && sel > 0) sel--;
        if (sel < top) top = sel;
        if (sel >= top + BODY_ROWS - 1) top = sel - (BODY_ROWS - 2);
        if (k == sk_Enter || k == sk_Del) {
            *key = k;
            return sel;
        }
    }
}

/* Ask for the password, then join and remember the network. */
static void join_new(const char *ssid) {
    char prompt[COLS + 1];
    snprintf(prompt, sizeof prompt, "Password for %s", ssid);
    /* [clear] on an empty password means an open network. */
    if (!get_text(prompt, MODE_LOWER, 63)) input[0] = '\0';
    snprintf(message, sizeof message, "WIFI:%s\t%s", ssid, input);
    request(message, "Joining...", 40);
    show_lines();
}

static void join_saved(const char *ssid) {
    snprintf(message, sizeof message, "JOIN:%s", ssid);
    request(message, "Joining...", 40);
    show_lines();
}

static void find_networks(void) {
    if (!request("SCAN", "Looking for Wi-Fi...", 40)) {
        show_lines();
        return;
    }
    static char found[MAX_NETWORKS][NAME_LEN + 1];
    int count = 0;
    for (int i = 0; i < line_count && count < MAX_NETWORKS; i++)
        if (line_kind[i] == 'N') strcpy(found[count++], lines[i]);
    if (count == 0) {
        show_lines();
        return;
    }
    uint8_t key;
    int sel = pick("Pick one (*=saved):", found, count, "enter: join  clear: back", is_saved, &key);
    if (sel < 0 || key != sk_Enter) return;
    if (is_saved(found[sel])) join_saved(found[sel]);
    else join_new(found[sel]);
}

static void type_network(void) {
    if (!get_text("Network name:", MODE_LOWER, NAME_LEN)) return;
    char ssid[NAME_LEN + 1];
    strcpy(ssid, input);
    join_new(ssid);
}

static void saved_networks(void) {
    for (;;) {
        load_saved();
        if (saved_count == 0) {
            show_message("No saved networks yet.", "enter: back");
            put_row(2, "Join one and it's saved.");
            wait_for_key();
            return;
        }
        uint8_t key;
        int sel = pick("Saved networks:", saved_names, saved_count, "enter=join del=forget", NULL, &key);
        if (sel < 0) return;
        if (key == sk_Enter) {
            join_saved(saved_names[sel]);
            return;
        }
        snprintf(message, sizeof message, "FORGET:%s", saved_names[sel]);
        request(message, "Forgetting...", QUICK_TIMEOUT);
        show_lines();
    }
}

static void wifi(void) {
    if (!require_link()) return;
    for (;;) {
        load_saved();
        clear_screen();
        put_row(0, "Wi-Fi");
        char row[COLS + 1];
        if (current_net[0]) snprintf(row, sizeof row, "On: %s", current_net);
        else snprintf(row, sizeof row, "Not connected");
        put_row(1, row);
        put_row(3, "1: Find networks");
        put_row(4, "2: Type a name+password");
        snprintf(row, sizeof row, "3: Saved networks (%d)", saved_count);
        put_row(5, row);
        put_row(7, "Saved ones join by");
        put_row(8, "themselves when in range.");
        put_row(ROWS - 1, "clear: back");
        uint8_t k;
        do {
            link_poll();
            k = os_GetCSC();
        } while (!k);
        if (k == sk_Clear) return;
        if (k == sk_1) find_networks();
        else if (k == sk_2) type_network();
        else if (k == sk_3) saved_networks();
        if (!link_ready()) return;
    }
}

/* ---------- credit ---------- */

static void credit(void) {
    for (;;) {
        if (!request("CREDIT", "Checking...", QUICK_TIMEOUT)) {
            show_lines();
            return;
        }
        clear_screen();
        for (int i = 0; i < line_count && i < BODY_ROWS - 2; i++) put_row((uint8_t)i, lines[i]);
        put_row(BODY_ROWS - 1, "1: Enter my balance");
        put_row(ROWS - 1, "clear: back");
        uint8_t k;
        do {
            link_poll();
            k = os_GetCSC();
        } while (!k);
        if (k != sk_1) return;
        if (!get_text("Balance in $ (like 4.95)", MODE_MATH, 10)) continue;
        snprintf(message, sizeof message, "CREDIT:%s", input);
        request(message, "Saving...", QUICK_TIMEOUT);
        show_lines();
    }
}

static void status(void) {
    request("STATUS", "Checking...", QUICK_TIMEOUT);
    show_lines();
}

static void credit_note(char *row, size_t size) {
    row[0] = '\0';
    if (credit_code == 1)
        snprintf(row, size, "! Credit low: ~$%ld.%02ld", credit_cents / 100, credit_cents % 100);
    else if (credit_code == 2)
        snprintf(row, size, "! Out of API credit");
    else if (credit_code == 3)
        snprintf(row, size, "Set your credit: press 4");
}

static void draw_menu(void) {
    clear_screen();
    put_row(0, "TI-84 Claude");
    put_row(1, "1: Ask a question");
    put_row(2, "2: Photo of a problem");
    put_row(3, "3: Wi-Fi");
    put_row(4, "4: Credit");
    put_row(5, "5: Status");
    put_row(7, link_ready() ? "Dongle: connected" : "Dongle: not plugged in");
    char row[COLS + 1];
    credit_note(row, sizeof row);
    put_row(8, row);
    put_row(ROWS - 1, "clear: quit");
}

int main(void) {
    os_ClrHome();
    if (!link_begin()) {
        show_message("USB didn't start.", "enter: quit");
        wait_for_key();
        return 0;
    }

    bool was_ready = !link_ready();
    for (;;) {
        if (link_ready() != was_ready) {
            was_ready = link_ready();
            draw_menu();
            if (was_ready && request("CREDIT", NULL, PING_TIMEOUT)) draw_menu(); /* for the warning line */
        }
        link_poll();
        uint8_t k = os_GetCSC();
        if (k == sk_Clear) break;
        bool acted = true;
        if (k == sk_1) ask_question();
        else if (k == sk_2) photo();
        else if (k == sk_3) wifi();
        else if (k == sk_4) credit();
        else if (k == sk_5) status();
        else acted = false;
        if (acted) draw_menu();
    }

    link_end();
    os_ClrHome();
    return 0;
}
