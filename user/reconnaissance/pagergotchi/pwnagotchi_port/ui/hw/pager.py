"""
Pager display driver for Pagergotchi
Uses native C library (libpager.so) for fast rendering

CRITICAL: This driver uses the native C library for rendering,
NOT PIL/Pillow (which is 5-30 seconds per frame on the Pager)
"""

import os
import ctypes
import logging

# Font sizes (match pager_gfx.h)
FONT_SMALL = 1
FONT_MEDIUM = 2
FONT_LARGE = 3
FONT_XLARGE = 4  # Extra large for face
FONT_XXLARGE = 5  # Even larger

# Button masks
PBTN_UP = 0x01
PBTN_DOWN = 0x02
PBTN_LEFT = 0x04
PBTN_RIGHT = 0x08
PBTN_A = 0x10    # RED button (LEFT side) - Back/Exit/Pause
PBTN_B = 0x20    # GREEN button (RIGHT side) - Select/Confirm

# Colors (RGB565)
COLOR_BLACK = 0x0000
COLOR_WHITE = 0xFFFF
COLOR_RED = 0xF800
COLOR_GREEN = 0x07E0
COLOR_BLUE = 0x001F
COLOR_YELLOW = 0xFFE0
COLOR_CYAN = 0x07FF
COLOR_GRAY = 0x8410


class PagerDisplay:
    """
    Native display driver for WiFi Pineapple Pager

    Display: 480x222 (landscape after rotation)
    Framebuffer: /dev/fb0
    Uses libpager.so for all rendering
    """

    def __init__(self, config=None):
        self._config = config or {}
        self._lib = None
        self._initialized = False

        # Display dimensions (landscape)
        self._width = 480
        self._height = 222

        # Find and load library
        self._load_library()

    def _load_library(self):
        """Load libpager.so"""
        search_paths = [
            '/root/payloads/user/reconnaissance/pagergotchi/lib/libpager.so',
            './lib/libpager.so',
            '../lib/libpager.so',
            '/usr/lib/libpager.so',
        ]

        lib_path = None
        for path in search_paths:
            if os.path.exists(path):
                lib_path = path
                break

        if lib_path is None:
            logging.warning("libpager.so not found - display will be simulated")
            self._lib = None
            return

        try:
            self._lib = ctypes.CDLL(lib_path)
            self._setup_functions()
            logging.info(f"Loaded display library: {lib_path}")
        except Exception as e:
            logging.error(f"Error loading libpager.so: {e}")
            self._lib = None

    def _setup_functions(self):
        """Set up ctypes function signatures"""
        if not self._lib:
            return

        # wrapper_init() -> int
        self._lib.wrapper_init.restype = ctypes.c_int
        self._lib.wrapper_init.argtypes = []

        # wrapper_cleanup()
        self._lib.wrapper_cleanup.restype = None
        self._lib.wrapper_cleanup.argtypes = []

        # wrapper_flip()
        self._lib.wrapper_flip.restype = None
        self._lib.wrapper_flip.argtypes = []

        # wrapper_clear(color)
        self._lib.wrapper_clear.restype = None
        self._lib.wrapper_clear.argtypes = [ctypes.c_uint16]

        # wrapper_get_width() -> int
        self._lib.wrapper_get_width.restype = ctypes.c_int
        self._lib.wrapper_get_width.argtypes = []

        # wrapper_get_height() -> int
        self._lib.wrapper_get_height.restype = ctypes.c_int
        self._lib.wrapper_get_height.argtypes = []

        # wrapper_fill_rect(x, y, w, h, color)
        self._lib.wrapper_fill_rect.restype = None
        self._lib.wrapper_fill_rect.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint16
        ]

        # wrapper_draw_text(x, y, text, color, size) -> int
        self._lib.wrapper_draw_text.restype = ctypes.c_int
        self._lib.wrapper_draw_text.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint16, ctypes.c_int
        ]

        # wrapper_draw_text_centered(y, text, color, size)
        self._lib.wrapper_draw_text_centered.restype = None
        self._lib.wrapper_draw_text_centered.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_uint16, ctypes.c_int
        ]

        # wrapper_text_width(text, size) -> int
        self._lib.wrapper_text_width.restype = ctypes.c_int
        self._lib.wrapper_text_width.argtypes = [ctypes.c_char_p, ctypes.c_int]

        # wrapper_hline(x, y, w, color)
        self._lib.wrapper_hline.restype = None
        self._lib.wrapper_hline.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint16
        ]

        # wrapper_poll_input(current*, pressed*, released*)
        self._lib.wrapper_poll_input.restype = None
        self._lib.wrapper_poll_input.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8)
        ]

    def initialize(self):
        """Initialize the display"""
        if self._initialized:
            return True

        if self._lib:
            try:
                result = self._lib.wrapper_init()
                if result == 0:
                    self._initialized = True
                    self._width = self._lib.wrapper_get_width()
                    self._height = self._lib.wrapper_get_height()
                    logging.info(f"Display initialized: {self._width}x{self._height}")
                    return True
            except Exception as e:
                logging.error(f"Display init error: {e}")

        return False

    def cleanup(self):
        """Clean up display resources"""
        if self._initialized and self._lib:
            try:
                self._lib.wrapper_cleanup()
            except:
                pass
        self._initialized = False

    def clear(self, color=COLOR_BLACK):
        """Clear screen with color"""
        if self._lib and self._initialized:
            self._lib.wrapper_clear(color)

    def flip(self):
        """Flip buffer to display"""
        if self._lib and self._initialized:
            self._lib.wrapper_flip()

    def draw_text(self, x, y, text, color=COLOR_WHITE, size=FONT_MEDIUM):
        """Draw text at position"""
        if self._lib and self._initialized:
            if isinstance(text, str):
                text = text.encode('utf-8', errors='replace')
            return self._lib.wrapper_draw_text(x, y, text, color, size)
        return 0

    def draw_text_centered(self, y, text, color=COLOR_WHITE, size=FONT_MEDIUM):
        """Draw centered text"""
        if self._lib and self._initialized:
            if isinstance(text, str):
                text = text.encode('utf-8', errors='replace')
            self._lib.wrapper_draw_text_centered(y, text, color, size)

    def text_width(self, text, size=FONT_MEDIUM):
        """Get text width in pixels"""
        if self._lib and self._initialized:
            if isinstance(text, str):
                text = text.encode('utf-8', errors='replace')
            return self._lib.wrapper_text_width(text, size)
        return len(text) * 6 if size == FONT_SMALL else len(text) * 10

    def fill_rect(self, x, y, w, h, color):
        """Draw filled rectangle"""
        if self._lib and self._initialized:
            self._lib.wrapper_fill_rect(x, y, w, h, color)

    def hline(self, x, y, w, color=COLOR_WHITE):
        """Draw horizontal line"""
        if self._lib and self._initialized:
            self._lib.wrapper_hline(x, y, w, color)

    def poll_input(self):
        """Poll for button input, returns (current, pressed, released)"""
        if self._lib and self._initialized:
            current = ctypes.c_uint8()
            pressed = ctypes.c_uint8()
            released = ctypes.c_uint8()
            self._lib.wrapper_poll_input(
                ctypes.byref(current),
                ctypes.byref(pressed),
                ctypes.byref(released)
            )
            return current.value, pressed.value, released.value
        return 0, 0, 0

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def layout(self):
        """Return UI layout for pager display (480x222)"""
        # Display: 480x222
        # Top bar: y=0-25 (channel, aps, uptime)
        # Line1: y=28 (separator)
        # Row 2: y=35 (name on left, status on right)
        # Face: y=60-180 (big ASCII face, left side)
        # Line2: y=185 (separator)
        # Bottom: y=192+ (shakes, mode)
        return {
            'width': 480,
            'height': 222,
            'name': (5, 55),         # Same line as status text
            'face': (10, 100),       # Big face, left side, with space below text
            'channel': (5, 0),       # CH 157(5G) needs ~120px
            'aps': (160, 0),         # Centered, more space for channel
            'uptime': (340, 0),      # Right side (was 350)
            'line1': [(0, 18), (480, 18)],  # Closer to top text to match bottom spacing
            'line2': [(0, 185), (480, 185)],
            'friend_face': (0, 45),
            'friend_name': (40, 47),
            'gps': (150, 166),  # GPS coordinates, above bottom bar
            'shakes': (5, 192),
            'mode': (350, 192),  # Battery indicator (moved left for BAT 100%+)
            'status': {
                'pos': (180, 55),    # Right of name, with clearance
                'font_size': FONT_MEDIUM,
                'max': 22            # Wrap earlier to prevent right-side cutoff
            }
        }

    def __del__(self):
        self.cleanup()
