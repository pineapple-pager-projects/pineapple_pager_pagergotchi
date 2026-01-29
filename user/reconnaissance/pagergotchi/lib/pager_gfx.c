/*
 * pager_gfx.c - WiFi Pineapple Pager Graphics Library Implementation
 */

#include "pager_gfx.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <errno.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <linux/fb.h>
#include <linux/input.h>

/* Framebuffer state */
static int fb_fd = -1;
static uint16_t *framebuffer = NULL;
static struct timeval start_time;

/* Input state */
static int input_fd = -1;
static uint8_t prev_buttons = 0;

/* Random state */
static uint32_t rand_state = 1;

/* Rotation state */
static pager_rotation_t current_rotation = ROTATION_0;
static int logical_width = PAGER_FB_WIDTH;
static int logical_height = PAGER_FB_HEIGHT;

/* 5x7 bitmap font (ASCII 32-127) */
static const uint8_t font_5x7[][5] = {
    {0x00,0x00,0x00,0x00,0x00}, /* 32 (space) */
    {0x00,0x00,0x5F,0x00,0x00}, /* 33 ! */
    {0x00,0x07,0x00,0x07,0x00}, /* 34 " */
    {0x14,0x7F,0x14,0x7F,0x14}, /* 35 # */
    {0x24,0x2A,0x7F,0x2A,0x12}, /* 36 $ */
    {0x23,0x13,0x08,0x64,0x62}, /* 37 % */
    {0x36,0x49,0x55,0x22,0x50}, /* 38 & */
    {0x00,0x05,0x03,0x00,0x00}, /* 39 ' */
    {0x00,0x1C,0x22,0x41,0x00}, /* 40 ( */
    {0x00,0x41,0x22,0x1C,0x00}, /* 41 ) */
    {0x08,0x2A,0x1C,0x2A,0x08}, /* 42 * */
    {0x08,0x08,0x3E,0x08,0x08}, /* 43 + */
    {0x00,0x50,0x30,0x00,0x00}, /* 44 , */
    {0x08,0x08,0x08,0x08,0x08}, /* 45 - */
    {0x00,0x60,0x60,0x00,0x00}, /* 46 . */
    {0x20,0x10,0x08,0x04,0x02}, /* 47 / */
    {0x3E,0x51,0x49,0x45,0x3E}, /* 48 0 */
    {0x00,0x42,0x7F,0x40,0x00}, /* 49 1 */
    {0x42,0x61,0x51,0x49,0x46}, /* 50 2 */
    {0x21,0x41,0x45,0x4B,0x31}, /* 51 3 */
    {0x18,0x14,0x12,0x7F,0x10}, /* 52 4 */
    {0x27,0x45,0x45,0x45,0x39}, /* 53 5 */
    {0x3C,0x4A,0x49,0x49,0x30}, /* 54 6 */
    {0x01,0x71,0x09,0x05,0x03}, /* 55 7 */
    {0x36,0x49,0x49,0x49,0x36}, /* 56 8 */
    {0x06,0x49,0x49,0x29,0x1E}, /* 57 9 */
    {0x00,0x36,0x36,0x00,0x00}, /* 58 : */
    {0x00,0x56,0x36,0x00,0x00}, /* 59 ; */
    {0x00,0x08,0x14,0x22,0x41}, /* 60 < */
    {0x14,0x14,0x14,0x14,0x14}, /* 61 = */
    {0x41,0x22,0x14,0x08,0x00}, /* 62 > */
    {0x02,0x01,0x51,0x09,0x06}, /* 63 ? */
    {0x32,0x49,0x79,0x41,0x3E}, /* 64 @ */
    {0x7E,0x11,0x11,0x11,0x7E}, /* 65 A */
    {0x7F,0x49,0x49,0x49,0x36}, /* 66 B */
    {0x3E,0x41,0x41,0x41,0x22}, /* 67 C */
    {0x7F,0x41,0x41,0x22,0x1C}, /* 68 D */
    {0x7F,0x49,0x49,0x49,0x41}, /* 69 E */
    {0x7F,0x09,0x09,0x01,0x01}, /* 70 F */
    {0x3E,0x41,0x41,0x51,0x32}, /* 71 G */
    {0x7F,0x08,0x08,0x08,0x7F}, /* 72 H */
    {0x00,0x41,0x7F,0x41,0x00}, /* 73 I */
    {0x20,0x40,0x41,0x3F,0x01}, /* 74 J */
    {0x7F,0x08,0x14,0x22,0x41}, /* 75 K */
    {0x7F,0x40,0x40,0x40,0x40}, /* 76 L */
    {0x7F,0x02,0x04,0x02,0x7F}, /* 77 M */
    {0x7F,0x04,0x08,0x10,0x7F}, /* 78 N */
    {0x3E,0x41,0x41,0x41,0x3E}, /* 79 O */
    {0x7F,0x09,0x09,0x09,0x06}, /* 80 P */
    {0x3E,0x41,0x51,0x21,0x5E}, /* 81 Q */
    {0x7F,0x09,0x19,0x29,0x46}, /* 82 R */
    {0x46,0x49,0x49,0x49,0x31}, /* 83 S */
    {0x01,0x01,0x7F,0x01,0x01}, /* 84 T */
    {0x3F,0x40,0x40,0x40,0x3F}, /* 85 U */
    {0x1F,0x20,0x40,0x20,0x1F}, /* 86 V */
    {0x7F,0x20,0x18,0x20,0x7F}, /* 87 W */
    {0x63,0x14,0x08,0x14,0x63}, /* 88 X */
    {0x03,0x04,0x78,0x04,0x03}, /* 89 Y */
    {0x61,0x51,0x49,0x45,0x43}, /* 90 Z */
    {0x00,0x00,0x7F,0x41,0x41}, /* 91 [ */
    {0x02,0x04,0x08,0x10,0x20}, /* 92 \ */
    {0x41,0x41,0x7F,0x00,0x00}, /* 93 ] */
    {0x04,0x02,0x01,0x02,0x04}, /* 94 ^ */
    {0x40,0x40,0x40,0x40,0x40}, /* 95 _ */
    {0x00,0x01,0x02,0x04,0x00}, /* 96 ` */
    {0x20,0x54,0x54,0x54,0x78}, /* 97 a */
    {0x7F,0x48,0x44,0x44,0x38}, /* 98 b */
    {0x38,0x44,0x44,0x44,0x20}, /* 99 c */
    {0x38,0x44,0x44,0x48,0x7F}, /* 100 d */
    {0x38,0x54,0x54,0x54,0x18}, /* 101 e */
    {0x08,0x7E,0x09,0x01,0x02}, /* 102 f */
    {0x08,0x14,0x54,0x54,0x3C}, /* 103 g */
    {0x7F,0x08,0x04,0x04,0x78}, /* 104 h */
    {0x00,0x44,0x7D,0x40,0x00}, /* 105 i */
    {0x20,0x40,0x44,0x3D,0x00}, /* 106 j */
    {0x00,0x7F,0x10,0x28,0x44}, /* 107 k */
    {0x00,0x41,0x7F,0x40,0x00}, /* 108 l */
    {0x7C,0x04,0x18,0x04,0x78}, /* 109 m */
    {0x7C,0x08,0x04,0x04,0x78}, /* 110 n */
    {0x38,0x44,0x44,0x44,0x38}, /* 111 o */
    {0x7C,0x14,0x14,0x14,0x08}, /* 112 p */
    {0x08,0x14,0x14,0x18,0x7C}, /* 113 q */
    {0x7C,0x08,0x04,0x04,0x08}, /* 114 r */
    {0x48,0x54,0x54,0x54,0x20}, /* 115 s */
    {0x04,0x3F,0x44,0x40,0x20}, /* 116 t */
    {0x3C,0x40,0x40,0x20,0x7C}, /* 117 u */
    {0x1C,0x20,0x40,0x20,0x1C}, /* 118 v */
    {0x3C,0x40,0x30,0x40,0x3C}, /* 119 w */
    {0x44,0x28,0x10,0x28,0x44}, /* 120 x */
    {0x0C,0x50,0x50,0x50,0x3C}, /* 121 y */
    {0x44,0x64,0x54,0x4C,0x44}, /* 122 z */
    {0x00,0x08,0x36,0x41,0x00}, /* 123 { */
    {0x00,0x00,0x7F,0x00,0x00}, /* 124 | */
    {0x00,0x41,0x36,0x08,0x00}, /* 125 } */
    {0x08,0x08,0x2A,0x1C,0x08}, /* 126 ~ */
    {0x08,0x1C,0x2A,0x08,0x08}, /* 127 DEL (arrow) */
};

#define FONT_WIDTH  5
#define FONT_HEIGHT 7
#define FONT_FIRST  32
#define FONT_LAST   127

/* Signal handler for clean exit */
static volatile int running = 1;

static void signal_handler(int sig) {
    (void)sig;
    running = 0;
}

/*
 * Initialization
 */

int pager_init(void) {
    struct fb_var_screeninfo vinfo;
    struct fb_fix_screeninfo finfo;

    /* Set up signal handlers */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    /* Open framebuffer */
    fb_fd = open("/dev/fb0", O_RDWR);
    if (fb_fd < 0) {
        perror("Failed to open /dev/fb0");
        return -1;
    }

    /* Get screen info (for verification) */
    if (ioctl(fb_fd, FBIOGET_VSCREENINFO, &vinfo) < 0) {
        perror("FBIOGET_VSCREENINFO");
        close(fb_fd);
        fb_fd = -1;
        return -1;
    }

    if (ioctl(fb_fd, FBIOGET_FSCREENINFO, &finfo) < 0) {
        perror("FBIOGET_FSCREENINFO");
        close(fb_fd);
        fb_fd = -1;
        return -1;
    }

    /* Verify dimensions */
    if (vinfo.xres != PAGER_FB_WIDTH || vinfo.yres != PAGER_FB_HEIGHT) {
        fprintf(stderr, "Warning: Expected %dx%d, got %dx%d\n",
                PAGER_FB_WIDTH, PAGER_FB_HEIGHT, vinfo.xres, vinfo.yres);
    }

    /* Allocate framebuffer */
    framebuffer = (uint16_t *)malloc(PAGER_FB_WIDTH * PAGER_FB_HEIGHT * sizeof(uint16_t));
    if (!framebuffer) {
        perror("Failed to allocate framebuffer");
        close(fb_fd);
        fb_fd = -1;
        return -1;
    }

    /* Clear to black */
    memset(framebuffer, 0, PAGER_FB_WIDTH * PAGER_FB_HEIGHT * sizeof(uint16_t));

    /* Open input device */
    input_fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    if (input_fd < 0) {
        /* Try event1 as fallback */
        input_fd = open("/dev/input/event1", O_RDONLY | O_NONBLOCK);
    }
    if (input_fd < 0) {
        fprintf(stderr, "Warning: Could not open input device\n");
    }

    /* Initialize timing */
    gettimeofday(&start_time, NULL);

    /* Seed random with time */
    pager_seed_random(pager_get_ticks());

    return 0;
}

/*
 * Rotation support
 */

void pager_set_rotation(pager_rotation_t rotation) {
    current_rotation = rotation;
    switch (rotation) {
        case ROTATION_90:
        case ROTATION_270:
            logical_width = PAGER_FB_HEIGHT;   /* 480 */
            logical_height = PAGER_FB_WIDTH;   /* 222 */
            break;
        default:  /* ROTATION_0, ROTATION_180 */
            logical_width = PAGER_FB_WIDTH;    /* 222 */
            logical_height = PAGER_FB_HEIGHT;  /* 480 */
            break;
    }
}

int pager_get_width(void) {
    return logical_width;
}

int pager_get_height(void) {
    return logical_height;
}

/* Transform logical coordinates to framebuffer coordinates based on rotation */
static void transform_coords(int lx, int ly, int *fx, int *fy) {
    switch (current_rotation) {
        case ROTATION_0:   /* No rotation */
            *fx = lx;
            *fy = ly;
            break;
        case ROTATION_90:  /* 90° CW: (lx,ly) -> (ly, 479-lx) for 480x222 logical */
            *fx = ly;
            *fy = PAGER_FB_HEIGHT - 1 - lx;
            break;
        case ROTATION_180: /* 180°: (lx,ly) -> (221-lx, 479-ly) */
            *fx = PAGER_FB_WIDTH - 1 - lx;
            *fy = PAGER_FB_HEIGHT - 1 - ly;
            break;
        case ROTATION_270: /* 270° CW (90° CCW): (lx,ly) -> (221-ly, lx) for 480x222 logical */
            *fx = PAGER_FB_WIDTH - 1 - ly;
            *fy = lx;
            break;
        default:
            *fx = lx;
            *fy = ly;
            break;
    }
}

/* Raw pixel write (no rotation, direct to framebuffer) */
static void raw_set_pixel(int fx, int fy, uint16_t color) {
    if (!framebuffer) return;
    if (fx < 0 || fx >= PAGER_FB_WIDTH || fy < 0 || fy >= PAGER_FB_HEIGHT) return;
    framebuffer[fy * PAGER_FB_WIDTH + fx] = color;
}

void pager_cleanup(void) {
    if (framebuffer) {
        /* Clear screen on exit */
        memset(framebuffer, 0, PAGER_FB_WIDTH * PAGER_FB_HEIGHT * sizeof(uint16_t));
        pager_flip();

        free(framebuffer);
        framebuffer = NULL;
    }

    if (fb_fd >= 0) {
        close(fb_fd);
        fb_fd = -1;
    }

    if (input_fd >= 0) {
        close(input_fd);
        input_fd = -1;
    }
}

/*
 * Frame management
 */

void pager_flip(void) {
    if (fb_fd >= 0 && framebuffer) {
        lseek(fb_fd, 0, SEEK_SET);
        write(fb_fd, framebuffer, PAGER_FB_WIDTH * PAGER_FB_HEIGHT * sizeof(uint16_t));
    }
}

void pager_clear(uint16_t color) {
    if (!framebuffer) return;

    if (color == 0) {
        memset(framebuffer, 0, PAGER_FB_WIDTH * PAGER_FB_HEIGHT * sizeof(uint16_t));
    } else {
        for (int i = 0; i < PAGER_FB_WIDTH * PAGER_FB_HEIGHT; i++) {
            framebuffer[i] = color;
        }
    }
}

uint32_t pager_get_ticks(void) {
    struct timeval now;
    gettimeofday(&now, NULL);
    return (uint32_t)((now.tv_sec - start_time.tv_sec) * 1000 +
                      (now.tv_usec - start_time.tv_usec) / 1000);
}

void pager_delay(uint32_t ms) {
    usleep(ms * 1000);
}

uint32_t pager_frame_sync(void) {
    static uint32_t last_frame = 0;
    uint32_t now = pager_get_ticks();
    uint32_t elapsed = now - last_frame;

    if (elapsed < PAGER_FRAME_MS) {
        pager_delay(PAGER_FRAME_MS - elapsed);
        now = pager_get_ticks();
        elapsed = now - last_frame;
    }

    last_frame = now;
    return elapsed;
}

/*
 * Drawing primitives
 */

void pager_set_pixel(int x, int y, uint16_t color) {
    if (!framebuffer) return;
    if (x < 0 || x >= logical_width || y < 0 || y >= logical_height) return;

    int fx, fy;
    transform_coords(x, y, &fx, &fy);
    raw_set_pixel(fx, fy, color);
}

void pager_fill_rect(int x, int y, int w, int h, uint16_t color) {
    if (!framebuffer) return;

    /* Clip to logical screen */
    int x1 = MAX(0, x);
    int y1 = MAX(0, y);
    int x2 = MIN(logical_width, x + w);
    int y2 = MIN(logical_height, y + h);

    /* For no rotation, use fast path */
    if (current_rotation == ROTATION_0) {
        for (int py = y1; py < y2; py++) {
            uint16_t *row = &framebuffer[py * PAGER_FB_WIDTH + x1];
            for (int px = x1; px < x2; px++) {
                *row++ = color;
            }
        }
    } else {
        /* With rotation, use pager_set_pixel for correctness */
        for (int py = y1; py < y2; py++) {
            for (int px = x1; px < x2; px++) {
                pager_set_pixel(px, py, color);
            }
        }
    }
}

void pager_draw_rect(int x, int y, int w, int h, uint16_t color) {
    pager_hline(x, y, w, color);
    pager_hline(x, y + h - 1, w, color);
    pager_vline(x, y, h, color);
    pager_vline(x + w - 1, y, h, color);
}

void pager_hline(int x, int y, int w, uint16_t color) {
    if (!framebuffer) return;
    if (y < 0 || y >= logical_height) return;

    int x1 = MAX(0, x);
    int x2 = MIN(logical_width, x + w);

    if (current_rotation == ROTATION_0) {
        uint16_t *row = &framebuffer[y * PAGER_FB_WIDTH + x1];
        for (int px = x1; px < x2; px++) {
            *row++ = color;
        }
    } else {
        for (int px = x1; px < x2; px++) {
            pager_set_pixel(px, y, color);
        }
    }
}

void pager_vline(int x, int y, int h, uint16_t color) {
    if (!framebuffer) return;
    if (x < 0 || x >= logical_width) return;

    int y1 = MAX(0, y);
    int y2 = MIN(logical_height, y + h);

    if (current_rotation == ROTATION_0) {
        for (int py = y1; py < y2; py++) {
            framebuffer[py * PAGER_FB_WIDTH + x] = color;
        }
    } else {
        for (int py = y1; py < y2; py++) {
            pager_set_pixel(x, py, color);
        }
    }
}

void pager_draw_line(int x0, int y0, int x1, int y1, uint16_t color) {
    int dx = ABS(x1 - x0);
    int dy = ABS(y1 - y0);
    int sx = x0 < x1 ? 1 : -1;
    int sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;

    while (1) {
        pager_set_pixel(x0, y0, color);

        if (x0 == x1 && y0 == y1) break;

        int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y0 += sy;
        }
    }
}

void pager_fill_circle(int cx, int cy, int r, uint16_t color) {
    for (int y = -r; y <= r; y++) {
        for (int x = -r; x <= r; x++) {
            if (x*x + y*y <= r*r) {
                pager_set_pixel(cx + x, cy + y, color);
            }
        }
    }
}

void pager_draw_circle(int cx, int cy, int r, uint16_t color) {
    int x = r;
    int y = 0;
    int err = 0;

    while (x >= y) {
        pager_set_pixel(cx + x, cy + y, color);
        pager_set_pixel(cx + y, cy + x, color);
        pager_set_pixel(cx - y, cy + x, color);
        pager_set_pixel(cx - x, cy + y, color);
        pager_set_pixel(cx - x, cy - y, color);
        pager_set_pixel(cx - y, cy - x, color);
        pager_set_pixel(cx + y, cy - x, color);
        pager_set_pixel(cx + x, cy - y, color);

        y++;
        err += 1 + 2*y;
        if (2*(err - x) + 1 > 0) {
            x--;
            err += 1 - 2*x;
        }
    }
}

/*
 * Text rendering
 */

int pager_draw_char(int x, int y, char c, uint16_t color, font_size_t size) {
    if (c < FONT_FIRST || c > FONT_LAST) c = '?';

    const uint8_t *glyph = font_5x7[c - FONT_FIRST];
    int scale = (int)size;

    for (int col = 0; col < FONT_WIDTH; col++) {
        uint8_t column = glyph[col];
        for (int row = 0; row < FONT_HEIGHT; row++) {
            if (column & (1 << row)) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        pager_set_pixel(x + col * scale + sx,
                                       y + row * scale + sy,
                                       color);
                    }
                }
            }
        }
    }

    return (FONT_WIDTH + 1) * scale;
}

int pager_draw_text(int x, int y, const char *text, uint16_t color, font_size_t size) {
    int start_x = x;

    while (*text) {
        if (*text == '\n') {
            x = start_x;
            y += (FONT_HEIGHT + 1) * (int)size;
        } else {
            x += pager_draw_char(x, y, *text, color, size);
        }
        text++;
    }

    return x - start_x;
}

void pager_draw_text_centered(int y, const char *text, uint16_t color, font_size_t size) {
    int width = pager_text_width(text, size);
    int x = (logical_width - width) / 2;
    pager_draw_text(x, y, text, color, size);
}

int pager_text_width(const char *text, font_size_t size) {
    int width = 0;
    int scale = (int)size;

    while (*text) {
        if (*text != '\n') {
            width += (FONT_WIDTH + 1) * scale;
        }
        text++;
    }

    if (width > 0) width -= scale; /* Remove trailing space */
    return width;
}

int pager_draw_number(int x, int y, int num, uint16_t color, font_size_t size) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%d", num);
    return pager_draw_text(x, y, buf, color, size);
}

/*
 * Input handling
 */

/* Linux evdev key codes for Pager buttons */
#define KEY_PAGER_UP     103  /* KEY_UP */
#define KEY_PAGER_DOWN   108  /* KEY_DOWN */
#define KEY_PAGER_LEFT   105  /* KEY_LEFT */
#define KEY_PAGER_RIGHT  106  /* KEY_RIGHT */
#define KEY_PAGER_A      304  /* BTN_SOUTH (Green/A) */
#define KEY_PAGER_B      305  /* BTN_EAST (Red/B) */

void pager_poll_input(pager_input_t *input) {
    struct input_event ev;
    uint8_t new_buttons = prev_buttons;

    if (input_fd < 0) {
        input->current = 0;
        input->pressed = 0;
        input->released = 0;
        return;
    }

    /* Read all pending events */
    while (read(input_fd, &ev, sizeof(ev)) == sizeof(ev)) {
        if (ev.type != EV_KEY) continue;

        uint8_t btn = 0;
        switch (ev.code) {
            case KEY_PAGER_UP:    btn = PBTN_UP;    break;
            case KEY_PAGER_DOWN:  btn = PBTN_DOWN;  break;
            case KEY_PAGER_LEFT:  btn = PBTN_LEFT;  break;
            case KEY_PAGER_RIGHT: btn = PBTN_RIGHT; break;
            case KEY_PAGER_A:     btn = PBTN_A;     break;
            case KEY_PAGER_B:     btn = PBTN_B;     break;
            default: continue;
        }

        if (ev.value == 1) {
            new_buttons |= btn;  /* Press */
        } else if (ev.value == 0) {
            new_buttons &= ~btn; /* Release */
        }
    }

    input->current = new_buttons;
    input->pressed = new_buttons & ~prev_buttons;
    input->released = ~new_buttons & prev_buttons;

    prev_buttons = new_buttons;
}

pager_button_t pager_wait_button(void) {
    pager_input_t input;

    /* Clear any pending input */
    pager_poll_input(&input);

    while (running) {
        pager_poll_input(&input);
        if (input.pressed) {
            return (pager_button_t)input.pressed;
        }
        pager_delay(10);
    }

    return BTN_NONE;
}

/*
 * Utility functions
 */

int pager_random(int max) {
    if (max <= 0) return 0;

    /* xorshift32 */
    rand_state ^= rand_state << 13;
    rand_state ^= rand_state >> 17;
    rand_state ^= rand_state << 5;

    return (int)(rand_state % (uint32_t)max);
}

void pager_seed_random(uint32_t seed) {
    rand_state = seed ? seed : 1;
}

/*
 * Audio - RTTTL playback via system RINGTONE command
 */

static pid_t audio_pid = 0;

/* Note frequencies (C4 = middle C = 262 Hz) */
static const int note_freqs[] = {
    /* C     C#    D     D#    E     F     F#    G     G#    A     A#    B  */
       262,  277,  294,  311,  330,  349,  370,  392,  415,  440,  466,  494,  /* Octave 4 */
};

/* Get frequency for a note (0=C, 1=C#, ... 11=B) and octave (1-8) */
static int get_note_freq(int note, int octave) {
    int base_freq = note_freqs[note % 12];
    int oct_diff = octave - 4;
    if (oct_diff > 0) {
        while (oct_diff-- > 0) base_freq *= 2;
    } else if (oct_diff < 0) {
        while (oct_diff++ < 0) base_freq /= 2;
    }
    return base_freq;
}

/* Play a single tone using the buzzer sysfs interface */
static void buzzer_tone(int freq, int duration_ms) {
    FILE *f;

    if (freq > 0) {
        f = fopen("/sys/class/leds/buzzer/frequency", "w");
        if (f) { fprintf(f, "%d", freq); fclose(f); }

        f = fopen("/sys/class/leds/buzzer/brightness", "w");
        if (f) { fprintf(f, "255"); fclose(f); }
    }

    usleep(duration_ms * 1000);

    f = fopen("/sys/class/leds/buzzer/brightness", "w");
    if (f) { fprintf(f, "0"); fclose(f); }
}

/* Parse and play RTTTL in child process */
static void play_rtttl_child(const char *rtttl) {
    /* Skip name (everything before first colon) */
    const char *p = strchr(rtttl, ':');
    if (!p) return;
    p++;

    /* Parse defaults: d=duration, o=octave, b=bpm */
    int def_duration = 4;
    int def_octave = 5;
    int bpm = 120;

    while (*p && *p != ':') {
        while (*p == ' ' || *p == ',') p++;
        if (*p == 'd' && *(p+1) == '=') {
            p += 2;
            def_duration = atoi(p);
            while (*p >= '0' && *p <= '9') p++;
        } else if (*p == 'o' && *(p+1) == '=') {
            p += 2;
            def_octave = atoi(p);
            while (*p >= '0' && *p <= '9') p++;
        } else if (*p == 'b' && *(p+1) == '=') {
            p += 2;
            bpm = atoi(p);
            while (*p >= '0' && *p <= '9') p++;
        } else {
            p++;
        }
    }

    if (*p == ':') p++;

    /* Calculate whole note duration in ms */
    int whole_note_ms = (60 * 1000 * 4) / bpm;

    /* Parse and play notes */
    while (*p) {
        while (*p == ' ' || *p == ',') p++;
        if (!*p) break;

        /* Parse duration (optional, before note) */
        int duration = def_duration;
        if (*p >= '0' && *p <= '9') {
            duration = atoi(p);
            while (*p >= '0' && *p <= '9') p++;
        }

        /* Parse note */
        int note = -1;  /* -1 = rest */
        switch (*p) {
            case 'c': case 'C': note = 0; break;
            case 'd': case 'D': note = 2; break;
            case 'e': case 'E': note = 4; break;
            case 'f': case 'F': note = 5; break;
            case 'g': case 'G': note = 7; break;
            case 'a': case 'A': note = 9; break;
            case 'b': case 'B': note = 11; break;
            case 'h': case 'H': note = 11; break;  /* European B */
            case 'p': case 'P': note = -1; break;  /* Pause/rest */
        }
        if (*p) p++;

        /* Check for sharp */
        if (*p == '#') {
            if (note >= 0) note++;
            p++;
        }

        /* Check for dotted note */
        int dotted = 0;
        if (*p == '.') {
            dotted = 1;
            p++;
        }

        /* Parse octave (optional, after note) */
        int octave = def_octave;
        if (*p >= '0' && *p <= '9') {
            octave = *p - '0';
            p++;
        }

        /* Check for dotted note again (can appear after octave) */
        if (*p == '.') {
            dotted = 1;
            p++;
        }

        /* Calculate duration in ms */
        int note_ms = whole_note_ms / duration;
        if (dotted) note_ms = note_ms + note_ms / 2;

        /* Play the note */
        if (note >= 0) {
            int freq = get_note_freq(note, octave);
            buzzer_tone(freq, note_ms * 9 / 10);  /* 90% tone, 10% gap */
            usleep(note_ms * 1000 / 10);  /* Small gap between notes */
        } else {
            usleep(note_ms * 1000);  /* Rest */
        }
    }
}

void pager_play_rtttl(const char *rtttl) {
    /* Stop any existing audio first */
    pager_stop_audio();

    /* Fork to play in background */
    audio_pid = fork();
    if (audio_pid == 0) {
        /* Child process - play RTTTL directly via buzzer sysfs */
        play_rtttl_child(rtttl);
        _exit(0);
    }
}

void pager_stop_audio(void) {
    /* Turn off the buzzer hardware FIRST */
    FILE *f = fopen("/sys/class/leds/buzzer/brightness", "w");
    if (f) { fprintf(f, "0"); fclose(f); }

    if (audio_pid > 0) {
        kill(audio_pid, SIGKILL);  /* Use SIGKILL for immediate stop */
        kill(-audio_pid, SIGKILL); /* Kill process group too */
        waitpid(audio_pid, NULL, WNOHANG);  /* Non-blocking wait */
        audio_pid = 0;
    }

    /* Kill any stray audio processes */
    system("killall -9 RINGTONE 2>/dev/null");

    /* Turn off buzzer again to be sure */
    f = fopen("/sys/class/leds/buzzer/brightness", "w");
    if (f) { fprintf(f, "0"); fclose(f); }
}

int pager_audio_playing(void) {
    if (audio_pid <= 0) return 0;

    int status;
    pid_t result = waitpid(audio_pid, &status, WNOHANG);
    if (result == audio_pid) {
        /* Process finished */
        audio_pid = 0;
        return 0;
    }
    return 1;
}
