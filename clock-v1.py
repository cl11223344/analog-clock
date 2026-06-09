from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import QTimer, Qt, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QPalette
import sys
import math
from datetime import datetime

class AnalogClock(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 250)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(80)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.opacity_slider)
        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)
        self.old_pos = None

    def change_opacity(self, value):
        self.setWindowOpacity(value / 100.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Draw clock face
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(10, 10, 180, 180)
        # Draw numbers except 12
        for i in range(1, 12):
            angle = i * 30
            x = 100 + 80 * math.sin(math.radians(angle))
            y = 100 - 80 * math.cos(math.radians(angle))
            painter.drawText(int(x-5), int(y+5), str(i))
        # Get current time
        now = datetime.now()
        hour = now.hour % 12
        minute = now.minute
        second = now.second
        # Draw hour hand
        hour_angle = (hour * 30) + (minute * 0.5)
        painter.setPen(QPen(Qt.black, 4))
        painter.drawLine(100, 100, int(100 + 50 * math.sin(math.radians(hour_angle))), int(100 - 50 * math.cos(math.radians(hour_angle))))
        # Minute hand
        min_angle = minute * 6
        painter.setPen(QPen(Qt.black, 3))
        painter.drawLine(100, 100, int(100 + 70 * math.sin(math.radians(min_angle))), int(100 - 70 * math.cos(math.radians(min_angle))))
        # Second hand
        sec_angle = second * 6
        painter.setPen(QPen(Qt.red, 2))
        painter.drawLine(100, 100, int(100 + 80 * math.sin(math.radians(sec_angle))), int(100 - 80 * math.cos(math.radians(sec_angle))))
        # Draw 12 on top
        angle = 0
        x = 100 + 80 * math.sin(math.radians(angle))
        y = 100 - 80 * math.cos(math.radians(angle))
        painter.drawText(int(x-5), int(y+5), "12")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    clock = AnalogClock()
    clock.show()
    sys.exit(app.exec_())

#cd /home/hrshl/Documents/Projects/analog-clock && /home/hrshl/Documents/Projects/.venv/bin/python clock.py