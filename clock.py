from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer, Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
import sys
import math
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

class AnalogClock(QWidget):
    CLOCK_SIZE = 140
    # smaller gap between stacked clocks to bring faces closer together
    CLOCK_SPACING = 6
    HORIZONTAL_PADDING = 20
    # reduce reserved right-side space so the window doesn't grab the cursor area
    SIDE_SLIDER_SPACE = 6
    CONTROLS_SPACE = 34
    # vertical gap between top clock and control buttons when placed above
    BUTTON_TOP_GAP = 44
    # (top control area reserved for controls)
    CLOCKS_HEIGHT = CLOCK_SIZE * 2 + CLOCK_SPACING
    WINDOW_HEIGHT = CLOCKS_HEIGHT + CONTROLS_SPACE
    WINDOW_WIDTH = CLOCK_SIZE + (HORIZONTAL_PADDING * 2) + SIDE_SLIDER_SPACE
    # (opacity control removed)
    COLOR_TRANSITION_SECONDS = 0.35
    CONTRAST_CHECK_SECONDS = 0.2
    KEEP_ON_TOP_SECONDS = 1.5

    def __init__(self):
        super().__init__()
        # start as always-on-top; double-click will toggle this
        self.always_on_top = True
        self.apply_always_on_top_flags()
        self.setAttribute(Qt.WA_TranslucentBackground)
        # keep the clock window at 60% opacity for consistent transparency
        self.setWindowOpacity(0.60)
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        # opacity controls removed; reserve a top control area instead
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update)
        self.clock_timer.start(1000)
        self.display_color = QColor(Qt.black)
        self.start_color = QColor(self.display_color)
        self.target_color = QColor(self.display_color)
        self.transition_started_at = time.monotonic()
        self.last_contrast_check = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_contrast_transition)
        self.animation_timer.start(16)
        self.visibility_timer = QTimer(self)
        self.visibility_timer.timeout.connect(self.ensure_on_top)
        self.visibility_timer.start(round(self.KEEP_ON_TOP_SECONDS * 1000))
        # timer to auto-restore always-on-top after a short snooze
        self.restore_timer = QTimer(self)
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self._restore_always_on_top)
        self.old_pos = None
        self.berlin_tz = ZoneInfo("Europe/Berlin")
        self.mumbai_tz = ZoneInfo("Asia/Kolkata")
        self.update_control_colors()
        # reserve a smaller top control area so the clock is closer to the cursor
        # reduce the invisible padding above the topmost clock
        self.top_control_offset = 12
        # enlarge window height to include the top control area
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT + self.top_control_offset)
        self.move_to_bottom_left()

    def apply_always_on_top_flags(self):
        flags = Qt.FramelessWindowHint | Qt.Tool
        # only add the always-on-top / bypass hint when requested
        if getattr(self, "always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
            if sys.platform.startswith("linux"):
                flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)

    def ensure_on_top(self):
        if self.windowState() & Qt.WindowMinimized:
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        if not self.isVisible():
            self.show()
        # only force raise when the clock is meant to stay on top
        if getattr(self, "always_on_top", True):
            self.raise_()

    def move_to_bottom_left(self):
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        left_margin = round(geometry.width() * 0.1)
        x = geometry.left() + left_margin
        y = self.bottom_y(geometry)
        self.move(x, y)

    def bottom_y(self, geometry):
        return geometry.bottom() - self.height() + 1

    def move_horizontally_at_bottom(self, delta_x):
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        min_x = geometry.left()
        max_x = geometry.right() - self.width() + 1
        x = max(min_x, min(self.x() + delta_x, max_x))
        self.move(x, self.bottom_y(geometry))

    # opacity controls and top-positioning for buttons removed

    def update_control_colors(self):
        clock_color = QColor(self.display_color)
        border_color = self.opposite_color(clock_color)

    def battery_percent(self):
        power_supply_path = Path("/sys/class/power_supply")
        if not power_supply_path.exists():
            return None

        for battery_path in sorted(power_supply_path.glob("BAT*")):
            capacity_path = battery_path / "capacity"
            if not capacity_path.exists():
                continue

            try:
                return max(0, min(100, int(capacity_path.read_text().strip())))
            except (OSError, ValueError):
                continue

        return None

    def battery_power_state(self):
        power_supply_path = Path("/sys/class/power_supply")
        if not power_supply_path.exists():
            return None

        for battery_path in sorted(power_supply_path.glob("BAT*")):
            status_path = battery_path / "status"
            if not status_path.exists():
                continue

            try:
                status = status_path.read_text().strip().lower()
            except OSError:
                continue

            if status == "discharging":
                return "BAT"
            if status in ("charging", "full", "not charging"):
                return "AC"

        return None

    def keep_visible(self):
        if self.windowState() & Qt.WindowMinimized:
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        # respect the user's toggle: don't force-focus if not always-on-top
        if getattr(self, "always_on_top", True):
            self.raise_()
            self.activateWindow()

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange and self.windowState() & Qt.WindowMinimized:
            QTimer.singleShot(0, self.keep_visible)
            QTimer.singleShot(100, self.keep_visible)
        super().changeEvent(event)

    def contrast_color(self):
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return Qt.black

        center = self.mapToGlobal(self.rect().center())
        image = screen.grabWindow(
            0,
            center.x() - 15,
            center.y() - 15,
            30,
            30,
        ).toImage()

        if image.isNull():
            return Qt.black

        total_luminance = 0
        samples = 0
        for x in range(0, image.width(), 5):
            for y in range(0, image.height(), 5):
                color = QColor(image.pixel(x, y))
                total_luminance += (
                    0.2126 * color.red()
                    + 0.7152 * color.green()
                    + 0.0722 * color.blue()
                )
                samples += 1

        average_luminance = total_luminance / samples
        return Qt.white if average_luminance < 128 else Qt.black

    def update_contrast_transition(self):
        now = time.monotonic()
        if now - self.last_contrast_check >= self.CONTRAST_CHECK_SECONDS:
            self.last_contrast_check = now
            contrast_color = QColor(self.contrast_color())
            if contrast_color != self.target_color:
                self.start_color = QColor(self.display_color)
                self.target_color = contrast_color
                self.transition_started_at = now

        elapsed = now - self.transition_started_at
        progress = min(1.0, elapsed / self.COLOR_TRANSITION_SECONDS)
        eased = progress * progress * (3 - (2 * progress))
        red = self.start_color.red() + (self.target_color.red() - self.start_color.red()) * eased
        green = self.start_color.green() + (self.target_color.green() - self.start_color.green()) * eased
        blue = self.start_color.blue() + (self.target_color.blue() - self.start_color.blue()) * eased
        self.display_color = QColor(round(red), round(green), round(blue))
        self.update_control_colors()
        self.update()

    def opposite_color(self, color):
        return QColor(255 - color.red(), 255 - color.green(), 255 - color.blue())

    def draw_outlined_text(self, painter, rect, alignment, text, fill_color, border_color):
        painter.setPen(QPen(border_color))
        for dx, dy in (
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),           (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
        ):
            painter.drawText(rect.adjusted(dx, dy, dx, dy), alignment, text)

        painter.setPen(QPen(fill_color))
        painter.drawText(rect, alignment, text)

    def draw_outlined_hand(self, painter, center_x, center_y, length, angle, width, fill_color, border_color):
        end_x = int(center_x + length * math.sin(math.radians(angle)))
        end_y = int(center_y - length * math.cos(math.radians(angle)))
        halo_color = QColor(border_color)
        halo_color.setAlpha(115)

        painter.setPen(QPen(halo_color, width + 7, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(center_x), int(center_y), end_x, end_y)
        painter.setPen(QPen(border_color, width + 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(center_x), int(center_y), end_x, end_y)
        painter.setPen(QPen(fill_color, width, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(center_x), int(center_y), end_x, end_y)

        dot_radius = max(2, round(width * 0.75))
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(fill_color))
        painter.drawEllipse(QRectF(end_x - dot_radius, end_y - dot_radius, dot_radius * 2, dot_radius * 2))

    def draw_clock(self, painter, top_left_x, top_left_y, now):
        scale = self.CLOCK_SIZE / 200
        center_x = top_left_x + self.CLOCK_SIZE / 2
        center_y = top_left_y + self.CLOCK_SIZE / 2
        margin = 10 * scale
        face_size = self.CLOCK_SIZE - (margin * 2)
        number_radius = 80 * scale
        hour_hand = 48 * scale
        minute_hand = 68 * scale
        second_hand = 76 * scale
        clock_color = QColor(self.display_color)
        border_color = self.opposite_color(clock_color)
        face_color = QColor(border_color)
        face_color.setAlpha(42)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(face_color))
        painter.drawEllipse(int(top_left_x + margin), int(top_left_y + margin), int(face_size), int(face_size))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(clock_color, max(1, round(2 * scale))))
        painter.drawEllipse(int(top_left_x + margin), int(top_left_y + margin), int(face_size), int(face_size))

        number_font = painter.font()
        number_font.setPointSize(max(8, round(12 * scale)))
        painter.setFont(number_font)
        painter.setPen(QPen(clock_color))
        number_box = 22 * scale
        for i in range(1, 12):
            angle = i * 30
            x = center_x + number_radius * math.sin(math.radians(angle))
            y = center_y - number_radius * math.cos(math.radians(angle))
            self.draw_outlined_text(
                painter,
                QRectF(x - number_box / 2, y - number_box / 2, number_box, number_box),
                Qt.AlignCenter,
                str(i),
                clock_color,
                border_color,
            )
        angle = 0
        x = center_x + number_radius * math.sin(math.radians(angle))
        y = center_y - number_radius * math.cos(math.radians(angle))
        self.draw_outlined_text(
            painter,
            QRectF(x - number_box / 2, y - number_box / 2, number_box, number_box),
            Qt.AlignCenter,
            "12",
            clock_color,
            border_color,
        )

        hour = now.hour % 12
        minute = now.minute
        second = now.second
        hour_angle = (hour * 30) + (minute * 0.5)
        self.draw_outlined_hand(
            painter,
            center_x,
            center_y,
            hour_hand,
            hour_angle,
            max(3, round(6 * scale)),
            clock_color,
            border_color,
        )
        min_angle = minute * 6
        self.draw_outlined_hand(
            painter,
            center_x,
            center_y,
            minute_hand,
            min_angle,
            max(3, round(5 * scale)),
            clock_color,
            border_color,
        )
        sec_angle = second * 6
        self.draw_outlined_hand(
            painter,
            center_x,
            center_y,
            second_hand,
            sec_angle,
            max(2, round(3 * scale)),
            clock_color,
            border_color,
        )
        hub_radius = max(4, round(6 * scale))
        painter.setPen(QPen(border_color, 2))
        painter.setBrush(QBrush(clock_color))
        painter.drawEllipse(QRectF(center_x - hub_radius, center_y - hub_radius, hub_radius * 2, hub_radius * 2))
        painter.setBrush(Qt.NoBrush)

    def draw_battery_indicator(self, painter):
        percent = self.battery_percent()
        power_state = self.battery_power_state()
        label_width = 72
        # center the label under the stacked clocks and place it at the bottom
        clocks_left = self.HORIZONTAL_PADDING
        x = clocks_left + (self.CLOCK_SIZE / 2) - (label_width / 2)
        # place the battery indicator near the bottom of the window
        y = self.height() - 28
        clock_color = QColor(self.display_color)
        border_color = self.opposite_color(clock_color)

        label = "--%" if percent is None else f"{percent}%"
        if power_state is not None:
            label = f"{label} {power_state}"
        label_font = painter.font()
        label_font.setPointSize(10)
        painter.setFont(label_font)
        self.draw_outlined_text(
            painter,
            QRectF(x, y - 3, label_width, 24),
            Qt.AlignCenter,
            label,
            clock_color,
            border_color,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        berlin_now = datetime.now(self.berlin_tz)
        mumbai_now = datetime.now(self.mumbai_tz)
        scale = self.CLOCK_SIZE / 200
        margin = 10 * scale
        # Stack the two clocks vertically; account for reserved top control area
        clocks_x = self.HORIZONTAL_PADDING
        top_y = margin + getattr(self, 'top_control_offset', 0)
        self.draw_clock(painter, clocks_x, top_y, berlin_now)
        self.draw_clock(painter, clocks_x, top_y + self.CLOCK_SIZE + self.CLOCK_SPACING, mumbai_now)
        self.draw_battery_indicator(painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_always_on_top()

    def toggle_always_on_top(self):
        self.always_on_top = not getattr(self, "always_on_top", True)
        self.apply_always_on_top_flags()
        # re-show so the window manager applies new flags
        self.show()
        if self.always_on_top:
            # stop any pending auto-restore if user re-enabled early
            try:
                self.restore_timer.stop()
            except Exception:
                pass
            self.raise_()
            self.activateWindow()
        else:
            # send to background so user can interact with underlying UI
            # and schedule auto-restore after 5 seconds
            try:
                self.restore_timer.start(5000)
            except Exception:
                pass
            self.lower()

    def _restore_always_on_top(self):
        # called by the single-shot timer to restore the always-on-top state
        self.always_on_top = True
        self.apply_always_on_top_flags()
        self.show()
        self.raise_()
        self.activateWindow()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move_horizontally_at_bottom(delta.x())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    clock = AnalogClock()
    clock.show()
    sys.exit(app.exec_())

#cd /home/hrshl/Documents/Projects/analog-clock && /home/hrshl/Documents/Projects/.venv/bin/python clock.py
