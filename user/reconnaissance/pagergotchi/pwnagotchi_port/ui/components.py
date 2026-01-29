"""
UI Components for native Pager display
Simplified from original - no PIL dependency, uses native rendering
"""


class Widget:
    """Base widget class"""
    def __init__(self, xy=(0, 0), color=0):
        self.xy = xy
        self.color = color
        self.value = None

    def draw(self, display):
        """Draw widget to display (override in subclasses)"""
        pass


class Text(Widget):
    """Text widget with multi-line support"""
    def __init__(self, value="", position=(0, 0), font=None, color=0, wrap=False, max_length=0, png=False):
        super().__init__(position, color)
        self.value = value
        self.font = font
        self.wrap = wrap
        self.max_length = max_length
        self.font_size = 2  # FONT_MEDIUM by default

    def _is_mac_address(self, word):
        """Check if word looks like a MAC address (XX:XX:XX:XX:XX:XX)"""
        # Strip trailing punctuation
        clean = word.rstrip('!.,;:')
        # MAC addresses have 5 colons and are 17 chars
        return clean.count(':') >= 4 and len(clean) >= 14

    def _wrap_text(self, text, max_chars):
        """Wrap text to multiple lines, handling long words and MAC addresses"""
        if not text or max_chars <= 0:
            return [text] if text else []

        words = str(text).split(' ')
        lines = []
        current_line = ""

        for word in words:
            # If word itself is too long, truncate it
            if len(word) > max_chars:
                word = word[:max_chars - 2] + '..'

            # MAC addresses always go on their own line
            if self._is_mac_address(word):
                if current_line:
                    lines.append(current_line)
                lines.append(word)
                current_line = ""
            elif not current_line:
                current_line = word
            elif len(current_line) + 1 + len(word) <= max_chars:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def draw(self, display):
        if self.value is not None and display:
            # Determine color (0 = black text on white, non-zero = white text)
            color = 0xFFFF if self.color == 0 else 0x0000

            if self.wrap and self.max_length > 0:
                # Multi-line wrapped text
                lines = self._wrap_text(str(self.value), self.max_length)
                # Line height based on font size (roughly 16-20 pixels for FONT_MEDIUM)
                line_height = 18 if self.font_size == 2 else (14 if self.font_size == 1 else 24)
                y = self.xy[1]
                for line in lines:
                    display.draw_text(self.xy[0], y, line, color, self.font_size)
                    y += line_height
            else:
                # Single line
                display.draw_text(self.xy[0], self.xy[1], str(self.value), color, self.font_size)


class LabeledValue(Widget):
    """Label + value widget"""
    def __init__(self, label, value="", position=(0, 0), label_font=None, text_font=None, color=0, label_spacing=5):
        super().__init__(position, color)
        self.label = label
        self.value = value
        self.label_font = label_font
        self.text_font = text_font
        self.label_spacing = label_spacing
        self.font_size = 2  # FONT_MEDIUM

    def draw(self, display):
        if display:
            color = 0xFFFF if self.color == 0 else 0x0000
            if self.label:
                # Draw label
                display.draw_text(self.xy[0], self.xy[1], self.label, color, self.font_size)
                # Draw value after label
                label_width = len(self.label) * 10 + self.label_spacing
                display.draw_text(self.xy[0] + label_width, self.xy[1], str(self.value), color, self.font_size)
            else:
                display.draw_text(self.xy[0], self.xy[1], str(self.value), color, self.font_size)


class Line(Widget):
    """Line widget"""
    def __init__(self, xy, color=0, width=1):
        super().__init__(xy, color)
        self.width = width
        self.value = True  # Always "true" for state tracking

    def draw(self, display):
        if display and len(self.xy) >= 2:
            color = 0xFFFF if self.color == 0 else 0x0000
            # xy is [(x1, y1), (x2, y2)]
            x1, y1 = self.xy[0]
            x2, y2 = self.xy[1]
            # Draw horizontal line
            if y1 == y2:
                display.hline(min(x1, x2), y1, abs(x2 - x1), color)


class Rect(Widget):
    """Rectangle outline widget"""
    def __init__(self, xy, color=0):
        super().__init__(xy, color)
        self.value = True

    def draw(self, display):
        # Not implemented for native display
        pass


class FilledRect(Widget):
    """Filled rectangle widget"""
    def __init__(self, xy, color=0):
        super().__init__(xy, color)
        self.value = True

    def draw(self, display):
        if display and len(self.xy) >= 4:
            color = 0xFFFF if self.color == 0 else 0x0000
            x, y, x2, y2 = self.xy
            display.fill_rect(x, y, x2 - x, y2 - y, color)


class Bitmap(Widget):
    """Bitmap widget - not supported on native display"""
    def __init__(self, path, xy, color=0):
        super().__init__(xy, color)
        self.path = path
        self.value = path

    def draw(self, display):
        # Bitmaps not supported on native display
        pass
