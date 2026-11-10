"""
pagerctl.py - pure-Python graphics/input library for the WiFi Pineapple Pager.

A pure-Python Pager graphics/input library exposing the same `Pager` API used by
existing payloads.  It talks to the framebuffer via the firmware's UI_TAKEOVER
command + direct writes to /dev/fb0

Typical use:

    from pagerctl import Pager
    with Pager() as p:            # init() on enter, cleanup() on exit
        p.set_rotation(270)
        p.clear(p.rgb(0, 0, 32))
        p.draw_ttf(10, 10, "Hello", p.WHITE, "myfont.ttf", 24)
        p.flip()
        if p.wait_button() & Pager.BTN_A:
            ...

Env PAGERCTL_FAKE=1 runs off-device against an in-memory framebuffer (for host
testing): takeover/input/sound/LED become no-ops and flip() writes to
self._surface, readable as native RGB565.
Env PAGERCTL_EXTERNAL_TAKEOVER=1 means the launcher already holds UI_TAKEOVER for
the whole session, so init()/cleanup() skip their own takeover/release.
"""
import os, random, struct, subprocess, sys, threading, time
from collections import deque

NW, NH, BPP, STRIDE = 222, 480, 2, 444
FB_SIZE = STRIDE * NH
FB_DEV = "/dev/fb0"
INPUT_DEV = "/dev/input/event0"
_FAKE = bool(os.environ.get("PAGERCTL_FAKE"))


def _run(args):
    if _FAKE:
        return 0
    try:
        return subprocess.run(args, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=10).returncode
    except Exception:
        return -1


class Pager:
    # RGB565 colors
    BLACK = 0x0000; WHITE = 0xFFFF; RED = 0xF800; GREEN = 0x07E0
    BLUE = 0x001F; YELLOW = 0xFFE0; CYAN = 0x07FF; MAGENTA = 0xF81F
    ORANGE = 0xFD20; PURPLE = 0x8010; GRAY = 0x8410
    ROTATION_0 = 0; ROTATION_90 = 90; ROTATION_180 = 180; ROTATION_270 = 270
    FONT_SMALL = 1; FONT_MEDIUM = 2; FONT_LARGE = 3
    BTN_UP = 0x01; BTN_DOWN = 0x02; BTN_LEFT = 0x04; BTN_RIGHT = 0x08
    BTN_A = 0x10; BTN_B = 0x20; BTN_POWER = 0x40
    EVENT_NONE = 0; EVENT_PRESS = 1; EVENT_RELEASE = 2
    RTTTL_SOUND_ONLY = 0; RTTTL_SOUND_VIBRATE = 1; RTTTL_VIBRATE_ONLY = 2
    RTTTL_TETRIS = ("tetris:d=4,o=5,b=160:e6,8b,8c6,8d6,16e6,16d6,8c6,8b,a,8a,"
                    "8c6,e6,8d6,8c6,b,8b,8c6,d6,e6,c6,a,2a")
    RTTTL_GAME_OVER = "smbdeath:d=4,o=5,b=90:8p,16b,16f6,16p,16f6,16f.6,16e.6,16d6,16c6"
    RTTTL_LEVEL_UP = "levelup:d=16,o=5,b=200:c,e,g,c6,8p,g,c6,e6,8g6"

    _KEYMAP = {103: BTN_UP, 108: BTN_DOWN, 105: BTN_LEFT, 106: BTN_RIGHT,
               305: BTN_A, 304: BTN_B, 116: BTN_POWER}
    _EV_KEY = 1
    _EV_FMT = "<llHHi"   # input_event on 32-bit: timeval(8) + type,code(u16) + value(s32)
    _EV_SZ = 16

    def __init__(self):
        self._initialized = False
        self.rotation = self.ROTATION_270
        self.back = bytearray(FB_SIZE)       # native draw buffer
        self._surface = None                 # mmap (or fake bytearray)
        self._fd = None
        self._atlas = {}                     # font_path -> parsed atlas
        self._blob = {}                      # blob path -> parsed blob
        self._t0 = time.monotonic()
        self._events = deque(maxlen=128)     # (button, PRESS/RELEASE, ms)
        self._held = 0                       # currently-held bitmask
        self._pressed = 0                    # pressed since last poll_input()
        self._released = 0                   # released since last poll_input()
        self._ilock = threading.Lock()
        self._ifd = None
        self._running = False
        self._own_takeover = True   # set in init() from PAGERCTL_EXTERNAL_TAKEOVER
        self._invert = True

    # ----------------------------- lifecycle -----------------------------
    def init(self):
        # If the launcher (payload.sh) already holds UI_TAKEOVER for the whole
        # session, don't grab/release it per-process 
        self._own_takeover = not os.environ.get("PAGERCTL_EXTERNAL_TAKEOVER")
        if self._own_takeover:
            _run(["UI_TAKEOVER"])
        try:
            if _FAKE:
                self._surface = bytearray(FB_SIZE)
            else:
                # Panel updates on the write() syscall path; mmap
                # writes alone never refresh the display. 
                self._fd = os.open(FB_DEV, os.O_RDWR)
        except Exception as e:
            sys.stderr.write(f"pagerctl: fb open failed: {e}\n")
            if self._own_takeover:
                _run(["UI_RELEASE"])
            return -1
        self._initialized = True
        self._running = True
        if not _FAKE:
            try:
                self._ifd = os.open(INPUT_DEV, os.O_RDONLY)
            except Exception:
                self._ifd = None
            if self._ifd is not None:
                threading.Thread(target=self._input_loop, daemon=True).start()
        return 0

    def cleanup(self):
        if not self._initialized:
            return
        self._running = False
        try:
            if self._ifd is not None:
                os.close(self._ifd); self._ifd = None   # unblocks the reader thread
        except Exception:
            pass
        try:
            if self._fd is not None:
                os.close(self._fd)
        except Exception:
            pass
        if getattr(self, "_own_takeover", True):
            _run(["UI_RELEASE"])
        self._initialized = False

    def __enter__(self): self.init(); return self
    def __exit__(self, *a): self.cleanup(); return False

    # ----------------------------- geometry ------------------------------
    def set_rotation(self, rotation):
        self.rotation = rotation
        # flip() reverses the whole native buffer (a 180° rotation) to correct the
        # panel's physical mount. That is only right for the landscape native
        # mapping (rotation 270/90); portrait (rotation 0) is identity-mapped, so
        # reversing it renders the screen upside down. Invert for landscape only.
        self._invert = rotation in (90, 270)

    @property
    def width(self):
        return 480 if self.rotation in (90, 270) else 222

    @property
    def height(self):
        return 222 if self.rotation in (90, 270) else 480

    # --------------------------- color helpers ---------------------------
    @staticmethod
    def rgb(r, g, b): return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

    @staticmethod
    def hex_color(h): return Pager.rgb((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)

    # ------------------------- native coord model ------------------------
    def _box_native(self, x, y, w, h):
        """Logical box (x,y,w,h) -> (nrow0, ncol0, nrows, ncols) in native space."""
        if self.rotation == 270:
            return (480 - x - w, y, w, h)
        if self.rotation == 90:
            return (x, 222 - y - h, w, h)
        if self.rotation == 180:
            return (480 - y - h, 222 - x - w, h, w)
        return (y, x, h, w)

    # ----------------------------- frame ---------------------------------
    def flip(self):
        out = memoryview(self.back).cast("H")[::-1].tobytes() if self._invert else self.back
        if _FAKE:
            if self._surface is not None:
                self._surface[0:FB_SIZE] = out
        elif self._fd is not None:
            os.pwrite(self._fd, out, 0)

    def clear(self, color=0):
        self.back[0:FB_SIZE] = struct.pack("<H", color & 0xFFFF) * (FB_SIZE // 2)

    def get_ticks(self): return int((time.monotonic() - self._t0) * 1000)
    def delay(self, ms): time.sleep(ms / 1000.0)
    def frame_sync(self): time.sleep(0.016); return self.get_ticks()

    # --------------------------- primitives ------------------------------
    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        nr0, nc0, nrows, ncols = self._box_native(x, y, w, h)
        c2 = struct.pack("<H", color & 0xFFFF)
        row = c2 * ncols
        b = self.back
        for r in range(nrows):
            nrow = nr0 + r
            if 0 <= nrow < NH:
                off = nrow * STRIDE + nc0 * BPP
                if 0 <= nc0 and nc0 + ncols <= NW:
                    b[off:off + ncols * BPP] = row
    def rect(self, x, y, w, h, color):
        self.hline(x, y, w, color); self.hline(x, y + h - 1, w, color)
        self.vline(x, y, h, color); self.vline(x + w - 1, y, h, color)
    def hline(self, x, y, w, color): self.fill_rect(x, y, w, 1, color)
    def vline(self, x, y, h, color): self.fill_rect(x, y, 1, h, color)
    def pixel(self, x, y, color): self.fill_rect(x, y, 1, 1, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1: break
            e2 = 2 * err
            if e2 >= dy: err += dy; x0 += sx
            if e2 <= dx: err += dx; y0 += sy

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.hline(cx - dx, cy + dy, 2 * dx + 1, color)
    def circle(self, cx, cy, r, color):
        x = r; y = 0; err = 1 - r
        while x >= y:
            for px, py in ((x, y), (y, x), (-x, y), (-y, x), (x, -y), (y, -x), (-x, -y), (-y, -x)):
                self.pixel(cx + px, cy + py, color)
            y += 1
            if err < 0: err += 2 * y + 1
            else: x -= 1; err += 2 * (y - x) + 1

    # ------------------------------ fonts --------------------------------

    def _load_atlas(self, font_path):
        ap = os.path.splitext(font_path)[0] + ".fatlas"
        a = self._atlas.get(ap, 0)      # 0 = not loaded; None = known-missing
        if a != 0:
            return a
        try:
            d = open(ap, "rb").read()
        except Exception:
            self._atlas[ap] = None; return None
        o = 4; _, nrot = struct.unpack_from("<BB", d, o); o += 2   # skip version byte
        index = {}
        for _ in range(nrot):
            rot, nsz = struct.unpack_from("<HB", d, o); o += 3
            sizes = {}
            for _ in range(nsz):
                size, asc, lh, ng = struct.unpack_from("<BHHB", d, o); o += 6
                sizes[size] = (o, asc, lh, ng)    # byte offset to this size's glyphs
                for _ in range(ng):               # skip glyph data (no objects made)
                    _, _, _, nsp = struct.unpack_from("<BBBH", d, o)
                    o += 5 + nsp * 3
            index[rot] = sizes
        atlas = {"raw": d, "index": index, "cache": {}}
        self._atlas[ap] = atlas
        return atlas

    def _glyphs(self, atlas, rot, size):
        """Decode (and cache) the glyph table for one (rot, size)."""
        key = (rot, size)
        G = atlas["cache"].get(key)
        if G is not None:
            return G
        o, asc, lh, ng = atlas["index"][rot][size]
        d = atlas["raw"]; G = {}
        for _ in range(ng):
            cp, adv, grows, nsp = struct.unpack_from("<BBBH", d, o); o += 5
            spans = [struct.unpack_from("<BBB", d, o + i * 3) for i in range(nsp)]
            o += nsp * 3
            G[cp] = (adv, grows, spans)
        atlas["cache"][key] = G
        return G

    def _resolve(self, atlas, font_size):
        """Pick (rot, size, index_entry) for the requested size, or None."""
        idx = atlas["index"]
        rot = self.rotation if self.rotation in idx else sorted(idx)[0]
        sizes = idx[rot]
        if not sizes:
            return None
        want = int(round(font_size))
        size = want if want in sizes else min(sizes, key=lambda s: abs(s - want))
        return rot, size, sizes[size]

    def draw_ttf(self, x, y, text, color, font_path, font_size):
        atlas = self._load_atlas(font_path)
        if not atlas:
            return -1
        r = self._resolve(atlas, font_size)
        if not r:
            return -1
        rot, size, _ = r
        G = self._glyphs(atlas, rot, size)
        c2 = struct.pack("<H", color & 0xFFFF)
        b = self.back; pen = 0
        for ch in text:
            g = G.get(ord(ch))
            if not g:
                continue
            adv, grows, spans = g
            if rot == 270:
                base_row = 480 - (x + pen) - grows
                for (rr, c, ln) in spans:
                    nrow = base_row + rr; ncol = y + c
                    if 0 <= nrow < NH and 0 <= ncol and ncol + ln <= NW:
                        off = nrow * STRIDE + ncol * BPP
                        b[off:off + ln * BPP] = c2 * ln
            else:  # rot 0
                for (rr, c, ln) in spans:
                    nrow = y + rr; ncol = x + pen + c
                    if 0 <= nrow < NH and 0 <= ncol and ncol + ln <= NW:
                        off = nrow * STRIDE + ncol * BPP
                        b[off:off + ln * BPP] = c2 * ln
            pen += adv
        return pen

    def ttf_width(self, text, font_path, font_size):
        atlas = self._load_atlas(font_path)
        if not atlas:
            return 0
        r = self._resolve(atlas, font_size)
        if not r:
            return 0
        rot, size, _ = r
        G = self._glyphs(atlas, rot, size)
        return sum(G[ord(c)][0] for c in text if ord(c) in G)

    def ttf_height(self, font_path, font_size):
        atlas = self._load_atlas(font_path)
        if not atlas:
            return int(font_size)
        r = self._resolve(atlas, font_size)
        return r[2][2] if r else int(font_size)   # line_h from the index entry

    def draw_ttf_centered(self, y, text, color, font_path, font_size):
        w = self.ttf_width(text, font_path, font_size)
        self.draw_ttf((self.width - w) // 2, y, text, color, font_path, font_size)

    def draw_ttf_right(self, y, text, color, font_path, font_size, padding=0):
        w = self.ttf_width(text, font_path, font_size)
        self.draw_ttf(self.width - w - padding, y, text, color, font_path, font_size)

    # ---------------- built-in bitmap font (routed to a TTF) -------------
    _DEFAULT_FONT = None  # set to an Arial.fatlas-backed path if available

    def _builtin_font(self):
        if self._DEFAULT_FONT:
            return self._DEFAULT_FONT
        moddir = os.path.dirname(os.path.abspath(__file__))
        up = os.path.dirname(moddir)
        cands = [os.path.join(moddir, "Arial.ttf"), os.path.join(os.getcwd(), "Arial.ttf"),
                 os.path.join(up, "resources", "fonts", "Arial.ttf"),
                 os.path.join(up, "themes", "loki", "fonts", "Arial.ttf"),
                 os.path.join(moddir, "fonts", "Arial.ttf")]
        for cand in cands:
            if os.path.exists(os.path.splitext(cand)[0] + ".fatlas"):
                Pager._DEFAULT_FONT = cand; return cand
        return None

    def _size_px(self, size): return {1: 11, 2: 20, 3: 30}.get(size, max(8, size * 10))

    def draw_text(self, x, y, text, color, size=1):
        f = self._builtin_font()
        return self.draw_ttf(x, y, text, color, f, self._size_px(size)) if f else 0
    def draw_char(self, x, y, char, color, size=1):
        return self.draw_text(x, y, char, color, size)
    def draw_text_centered(self, y, text, color, size=1):
        f = self._builtin_font()
        if f: self.draw_ttf_centered(y, text, color, f, self._size_px(size))
    def text_width(self, text, size=1):
        f = self._builtin_font()
        return self.ttf_width(text, f, self._size_px(size)) if f else len(text) * 6 * size
    def draw_number(self, x, y, num, color, size=1):
        return self.draw_text(x, y, str(num), color, size)

    # ------------------------------ images -------------------------------
    def _prewarm_path(self, filepath, w, h, rot, ext):
        d = os.path.join(os.path.dirname(filepath), "prewarm")
        return os.path.join(d, f"{os.path.basename(filepath)}.{w}x{h}.r{rot}.{ext}")

    def _load_blob(self, path):
        if path in self._blob:
            return self._blob[path]
        try:
            d = open(path, "rb").read()
        except Exception:
            self._blob[path] = None; return None
        self._blob[path] = d
        return d

    def _blit_nbg(self, d, x, y, w, h):
        _, nr, nc = struct.unpack_from("<HHH", d, 4); o = 10   # rot, rows, cols
        nr0, nc0, _, _ = self._box_native(x, y, w, h)
        b = self.back
        for r in range(nr):
            nrow = nr0 + r
            if 0 <= nrow < NH and 0 <= nc0 and nc0 + nc <= NW:
                src = o + r * nc * BPP
                b[nrow * STRIDE + nc0 * BPP: nrow * STRIDE + (nc0 + nc) * BPP] = d[src:src + nc * BPP]

    def _blit_nspr(self, d, x, y, w, h):
        _, nr, nc = struct.unpack_from("<HHH", d, 4); o = 10   # rot, rows, cols
        nr0, nc0, _, _ = self._box_native(x, y, w, h)
        b = self.back
        for r in range(nr):
            (nruns,) = struct.unpack_from("<H", d, o); o += 2
            nrow = nr0 + r; valid = 0 <= nrow < NH
            for _ in range(nruns):
                col, ln = struct.unpack_from("<HH", d, o); o += 4
                px = d[o:o + ln * BPP]; o += ln * BPP
                if valid:
                    ncol = nc0 + col
                    if 0 <= ncol and ncol + ln <= NW:
                        off = nrow * STRIDE + ncol * BPP
                        b[off:off + ln * BPP] = px

    def draw_image_file_scaled(self, x, y, w, h, filepath):
        return self._draw_scaled(x, y, w, h, filepath, self.rotation)

    def draw_image_file_scaled_rotated(self, x, y, w, h, filepath, rotation=0):
        return self._draw_scaled(x, y, w, h, filepath, self.rotation)

    def _draw_scaled(self, x, y, w, h, filepath, rot):
        nbg = self._prewarm_path(filepath, w, h, rot, "nbg")
        d = self._load_blob(nbg)
        if d and d[:4] == b"NBG1":
            self._blit_nbg(d, x, y, w, h); return 0
        nspr = self._prewarm_path(filepath, w, h, rot, "nspr")
        d = self._load_blob(nspr)
        if d and d[:4] == b"NSPR":
            self._blit_nspr(d, x, y, w, h); return 0
        return -1

    def draw_image_file(self, x, y, filepath):
        info = self.get_image_info(filepath)
        if not info:
            return -1
        return self.draw_image_file_scaled(x, y, info[0], info[1], filepath)

    def get_image_info(self, filepath):
        d = self._load_blob(filepath + ".r565")
        if d and d[:4] == b"R565":
            _, w, h = struct.unpack_from("<BHH", d, 4)
            return (w, h)
        return None

    def load_image(self, filepath): return filepath
    def free_image(self, handle): pass
    def draw_image(self, x, y, handle):
        info = self.get_image_info(handle)
        if info: self.draw_image_file_scaled(x, y, info[0], info[1], handle)
    def draw_image_scaled(self, x, y, w, h, handle): self.draw_image_file_scaled(x, y, w, h, handle)
    def draw_image_scaled_rotated(self, x, y, w, h, handle, rotation=0):
        self.draw_image_file_scaled_rotated(x, y, w, h, handle, rotation)

    def screenshot(self, filepath, rotation=270):
        return -1  # on-device PNG writing not available without native codec

    # ------------------------------ input --------------------------------
    def _input_loop(self):
        # Blocking reads from /dev/input/event0; maintain held state + event queue.
        while self._running and self._ifd is not None:
            try:
                data = os.read(self._ifd, self._EV_SZ * 16)
            except OSError:
                break          # fd closed on cleanup
            if not data:
                break
            for off in range(0, len(data) - self._EV_SZ + 1, self._EV_SZ):
                _, _, etype, code, value = struct.unpack_from(self._EV_FMT, data, off)
                if etype != self._EV_KEY:
                    continue
                btn = self._KEYMAP.get(code)
                if not btn:
                    continue
                with self._ilock:
                    if value == 1:        # press
                        self._held |= btn; self._pressed |= btn
                        self._events.append((btn, self.EVENT_PRESS, self.get_ticks()))
                    elif value == 0:      # release
                        self._held &= ~btn; self._released |= btn
                        self._events.append((btn, self.EVENT_RELEASE, self.get_ticks()))
                    # value == 2 (autorepeat): ignore

    def wait_button(self):
        while self._running:
            ev = self.get_input_event()
            if ev and ev[1] == self.EVENT_PRESS:
                return ev[0]
            if ev is None:
                time.sleep(0.005)
        return 0
    def poll_input(self):
        with self._ilock:
            r = (self._held, self._pressed, self._released)
            self._pressed = 0; self._released = 0
        return r
    def get_input_event(self):
        try:
            return self._events.popleft()
        except IndexError:
            return None
    def has_input_events(self): return bool(self._events)
    def peek_buttons(self): return self._held
    def clear_input_events(self):
        self._events.clear()
        with self._ilock:
            self._pressed = 0; self._released = 0

    # ------------------------------ audio --------------------------------

    def play_rtttl(self, melody, mode=None):
        if mode == self.RTTTL_VIBRATE_ONLY:
            _run(["VIBRATE", melody])
        elif mode == self.RTTTL_SOUND_VIBRATE:
            _run(["RINGTONE", "--vibrate", melody])
        else:
            _run(["RINGTONE", melody])
    def play_rtttl_sync(self, melody, with_vibration=False):
        _run(["RINGTONE", "--vibrate", melody] if with_vibration else ["RINGTONE", melody])
    def stop_audio(self): pass
    def audio_playing(self): return False      
    def beep(self, freq, duration_ms):

        if _FAKE:
            return
        try:
            open(f"{self._LED_BASE}/buzzer/frequency", "w").write(str(int(freq)))
            open(f"{self._LED_BASE}/buzzer/brightness", "w").write("255")
            time.sleep(max(0, duration_ms) / 1000.0)
            open(f"{self._LED_BASE}/buzzer/brightness", "w").write("0")
        except Exception:
            pass

    # ---------------------------- vibration ------------------------------

    def vibrate(self, duration_ms=200):
        # single d=4 note; its length in ms = 60000/bpm  ->  bpm = 60000/ms
        bpm = max(25, min(900, round(60000 / max(1, duration_ms))))
        _run(["VIBRATE", f"v:d=4,o=5,b={bpm}:c"])
    def vibrate_pattern(self, pattern): _run(["VIBRATE", pattern])

    # ------------------------------- LEDs --------------------------------
    # Per-LED control via raw sysfs: full per-direction RGB + a/b button LEDs,
    # which the firmware's DPADLED command can't do. Safe because this library
    # issues no DPADLED/LED commands, so nothing in the firmware fights these writes.
    _LED_BASE = "/sys/class/leds"
    def _led_raw(self, name, value):
        if _FAKE:
            return
        try:
            open(f"{self._LED_BASE}/{name}/brightness", "w").write(str(int(max(0, min(255, value)))))
        except Exception:
            pass
    def led_set(self, name, brightness): self._led_raw(name, brightness)
    def led_rgb(self, button, r, g, b):
        for ch, v in (("red", r), ("green", g), ("blue", b)):
            self._led_raw(f"{button}-led-{ch}", v)
    def led_dpad(self, direction, color):
        self.led_rgb(direction, (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    def led_all_off(self):
        for d in ("up", "down", "left", "right"):
            self.led_rgb(d, 0, 0, 0)
        self._led_raw("a-button-led", 0)
        self._led_raw("b-button-led", 0)
    def led_status(self, state, pattern=None):
        """Optional: the firmware status LED via the LED DuckyScript command
        (colors/patterns/semantic states). This DOES use the daemon — don't mix
        with heavy raw LED use in the same instant."""
        _run(["LED", state] + ([pattern] if pattern else []))

    # ---------------------------- brightness -----------------------------

    def _bl_dir(self):
        base = "/sys/class/backlight"
        try:
            for d in os.listdir(base):
                return os.path.join(base, d)
        except Exception:
            pass
        return None
    def set_brightness(self, percent):
        """Set backlight brightness (0-100%) via sysfs.

        NOTE: under UI_TAKEOVER this does NOT stick — pagerOS owns the backlight
        and re-applies its own value on UI events, reverting the write within a
        moment. Useful only when the pager daemon is stopped (non-takeover
        payloads). Brightness for takeover payloads should be left to pagerOS.
        """
        d = self._bl_dir()
        if not d: return -1
        try:
            mx = int(open(os.path.join(d, "max_brightness")).read())
            open(os.path.join(d, "brightness"), "w").write(str(int(mx * percent / 100)))
            return 0
        except Exception:
            return -1
    def get_brightness(self):
        d = self._bl_dir()
        if not d: return -1
        try:
            mx = int(open(os.path.join(d, "max_brightness")).read())
            cur = int(open(os.path.join(d, "brightness")).read())
            return int(cur * 100 / mx)
        except Exception:
            return -1
    def get_max_brightness(self):
        d = self._bl_dir()
        try: return int(open(os.path.join(d, "max_brightness")).read())
        except Exception: return -1
    # On this panel the backlight goes dark at ~10% (below ~20% it stops lighting);
    # brightness 0 is a misbehaving special case, so screen_off uses 10%.
    def screen_off(self): return self.set_brightness(10)
    def screen_on(self): return self.set_brightness(80)

    # ------------------------------ random -------------------------------
    def random(self, max_val): return random.randrange(max_val) if max_val > 0 else 0
    def seed_random(self, seed): random.seed(seed)
