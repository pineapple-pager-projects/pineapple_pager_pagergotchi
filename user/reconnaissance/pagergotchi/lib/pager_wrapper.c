/*
 * pager_wrapper.c - Thin wrapper around pager_gfx for Python ctypes
 * Compile as shared library: libpager.so
 */

#include "pager_gfx.h"
#include "pager_gfx.c"  /* Include implementation directly for single-file build */

/* Export functions for Python ctypes */

/*
 * CRITICAL SETTINGS - DO NOT CHANGE WITHOUT TESTING ON DEVICE
 *
 * ROTATION: Must be ROTATION_270 for correct landscape orientation
 *           ROTATION_90 = upside down (WRONG)
 *           ROTATION_270 = correct orientation (matches Hakanoid)
 *
 * BUTTONS: As defined in pager_gfx.h:
 *           PBTN_A (0x10) = Green button (right side) = Select/Confirm
 *           PBTN_B (0x20) = Red button (left side) = Exit/Back
 */
int wrapper_init(void) {
    pager_set_rotation(ROTATION_270);  /* MUST be 270 for correct orientation */
    return pager_init();
}

void wrapper_cleanup(void) {
    pager_cleanup();
}

void wrapper_flip(void) {
    pager_flip();
}

void wrapper_clear(uint16_t color) {
    pager_clear(color);
}

int wrapper_get_width(void) {
    return pager_get_width();
}

int wrapper_get_height(void) {
    return pager_get_height();
}

void wrapper_fill_rect(int x, int y, int w, int h, uint16_t color) {
    pager_fill_rect(x, y, w, h, color);
}

void wrapper_draw_rect(int x, int y, int w, int h, uint16_t color) {
    pager_draw_rect(x, y, w, h, color);
}

int wrapper_draw_text(int x, int y, const char *text, uint16_t color, int size) {
    return pager_draw_text(x, y, text, color, (font_size_t)size);
}

void wrapper_draw_text_centered(int y, const char *text, uint16_t color, int size) {
    pager_draw_text_centered(y, text, color, (font_size_t)size);
}

int wrapper_text_width(const char *text, int size) {
    return pager_text_width(text, (font_size_t)size);
}

void wrapper_poll_input(uint8_t *current, uint8_t *pressed, uint8_t *released) {
    pager_input_t input;
    pager_poll_input(&input);
    *current = input.current;
    *pressed = input.pressed;
    *released = input.released;
}

void wrapper_draw_line(int x0, int y0, int x1, int y1, uint16_t color) {
    pager_draw_line(x0, y0, x1, y1, color);
}

void wrapper_hline(int x, int y, int w, uint16_t color) {
    pager_hline(x, y, w, color);
}

void wrapper_vline(int x, int y, int h, uint16_t color) {
    pager_vline(x, y, h, color);
}

uint32_t wrapper_get_ticks(void) {
    return pager_get_ticks();
}

void wrapper_delay(uint32_t ms) {
    pager_delay(ms);
}

/* RGB to RGB565 color conversion helper */
uint16_t wrapper_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}
