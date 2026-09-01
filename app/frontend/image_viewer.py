"""中间图像显示组件（objectName 化，paintEvent 自绘底色但不写局部 QSS）。

展示输入图像/推理结果，支持交互式区域绘制。无任何 setStyleSheet 调用。
"""
import cv2
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QSizePolicy, QWidget


class ImageViewer(QWidget):
    """图像查看器，支持自适应显示与区域绘制。"""

    region_committed = pyqtSignal(list)

    # 背景色（深蓝灰，视频/图像周围留白，Qt 原生 API 不走 QSS）
    BG_COLOR = QColor(31, 41, 55, 255)
    PLACEHOLDER_COLOR = QColor(180, 190, 200)
    DRAW_COLOR = QColor(46, 204, 113)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")   # 外框卡片圆角由全局 QSS 负责
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(480, 320)
        self._pixmap = None
        self._drawing = False
        self._points = []

    # ---------- 公共 API ----------
    def show_image(self, image):
        if image is None:
            return
        if image.ndim == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]
        qimg = QImage(image.data, w, h, image.strides[0], QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg).copy()
        self.update()

    def clear(self):
        self._pixmap = None
        self._drawing = False
        self._points.clear()
        self.update()

    def enter_drawing_mode(self, image):
        self.show_image(image)
        self._drawing = True
        self._points.clear()
        self.update()

    def exit_drawing_mode(self):
        self._drawing = False
        self._points.clear()
        self.update()

    def get_points(self):
        return [(p.x(), p.y()) for p in self._points]

    # ---------- 鼠标 ----------
    def mousePressEvent(self, event):
        if not self._drawing:
            return
        if event.button() == Qt.LeftButton:
            pt = self._w2i(event.pos())
            if pt is not None:
                self._points.append(pt)
                self.update()
        elif event.button() == Qt.RightButton:
            self._points.clear()
            self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), self.BG_COLOR)

        if self._pixmap is None:
            painter.setPen(self.PLACEHOLDER_COLOR)
            f = painter.font()
            f.setPointSize(12)
            painter.setFont(f)
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "点击左侧 [加载图像] 选择图片\n或选择 [视频跟踪] 开始视频分析")
            return

        scaled = self._pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        dx = int((self.width() - scaled.width()) / 2)
        dy = int((self.height() - scaled.height()) / 2)
        painter.drawPixmap(dx, dy, scaled)

        if self._drawing and self._points:
            sx = scaled.width() / max(1, self._pixmap.width())
            sy = scaled.height() / max(1, self._pixmap.height())
            disp = [QPointF(dx + p.x() * sx, dy + p.y() * sy) for p in self._points]
            painter.setPen(QPen(self.DRAW_COLOR, 2))
            painter.setBrush(Qt.NoBrush)
            if len(disp) >= 2:
                painter.drawPolyline(QPolygonF(disp))
            painter.setBrush(QBrush(self.DRAW_COLOR))
            for p in disp:
                painter.drawEllipse(p, 5, 5)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def _w2i(self, pos):
        """控件坐标 → 图像坐标。"""
        if self._pixmap is None:
            return None
        scaled = self._pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        dx = (self.width() - scaled.width()) / 2
        dy = (self.height() - scaled.height()) / 2
        dpx = pos.x() - dx
        dpy = pos.y() - dy
        if dpx < 0 or dpy < 0 or dpx >= scaled.width() or dpy >= scaled.height():
            return None
        sx = self._pixmap.width() / max(1, scaled.width())
        sy = self._pixmap.height() / max(1, scaled.height())
        return QPointF(dpx * sx, dpy * sy)
