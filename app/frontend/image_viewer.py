"""中间图像显示组件：浅色画布 + 自适应图像显示 + 交互式区域绘制。

视觉全部由 QPainter 自绘（圆角画布、渐变底、虚线占位框、区域多边形），
坐标换算逻辑与之前保持一致。
"""
import cv2
from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF,
)
from PyQt5.QtWidgets import QSizePolicy, QWidget

from app.frontend.theme import (
    COLOR_BORDER as THEME_BORDER,
    COLOR_CANVAS_BOTTOM as THEME_CANVAS_BOTTOM,
    COLOR_CANVAS_TOP as THEME_CANVAS_TOP,
    COLOR_DRAW as THEME_DRAW,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECOND,
)

RADIUS = 14

COLOR_CANVAS_TOP = QColor(THEME_CANVAS_TOP)
COLOR_CANVAS_BOTTOM = QColor(THEME_CANVAS_BOTTOM)
COLOR_BORDER = QColor(THEME_BORDER)
COLOR_PLACEHOLDER = QColor(COLOR_TEXT_MUTED)
COLOR_PLACEHOLDER_STRONG = QColor(COLOR_TEXT_SECOND)
COLOR_DASH = QColor("#c9d4e4")
COLOR_DRAW = QColor(THEME_DRAW)


class ImageViewer(QWidget):
    """图像查看器，支持自适应显示与区域绘制。"""

    region_committed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
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
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 圆角画布 + 渐变底
        canvas = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(canvas, RADIUS, RADIUS)
        painter.setClipPath(path)

        grad = QLinearGradient(0, 0, 0, max(1, self.height()))
        grad.setColorAt(0.0, COLOR_CANVAS_TOP)
        grad.setColorAt(1.0, COLOR_CANVAS_BOTTOM)
        painter.fillPath(path, QBrush(grad))

        if self._pixmap is None:
            self._paint_placeholder(painter)
        else:
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            dx = int((self.width() - scaled.width()) / 2)
            dy = int((self.height() - scaled.height()) / 2)
            painter.drawPixmap(dx, dy, scaled)
            if self._drawing:
                self._paint_region(painter, scaled, dx, dy)

        painter.setClipping(False)
        if self._drawing and self._points:
            self._paint_drawing_tip(painter)

        # 外描边（最后画，避免被裁剪）
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(COLOR_BORDER, 1))
        painter.drawPath(path)
        painter.end()

    def _paint_placeholder(self, painter):
        """无图像时的空态：虚线框 + 图标化文字。"""
        box = QRectF(self.rect()).adjusted(24, 24, -24, -24)
        pen = QPen(COLOR_DASH, 1.4, Qt.DashLine)
        pen.setDashPattern([6, 6])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(box, 12, 12)

        cx = self.width() / 2
        cy = self.height() / 2

        # 简易「画面」图标
        icon = QRectF(cx - 26, cy - 62, 52, 36)
        painter.setPen(QPen(COLOR_PLACEHOLDER_STRONG, 1.6))
        painter.drawRoundedRect(icon, 6, 6)
        painter.drawLine(QPointF(icon.left() + 6, icon.bottom() - 9),
                         QPointF(icon.left() + 18, icon.top() + 12))
        painter.drawLine(QPointF(icon.left() + 18, icon.top() + 12),
                         QPointF(icon.right() - 8, icon.bottom() - 9))

        title_font = QFont("Microsoft YaHei UI")
        title_font.setPointSize(13)
        title_font.setBold(True)
        body_font = QFont("Microsoft YaHei UI")
        body_font.setPointSize(10)

        painter.setFont(title_font)
        painter.setPen(COLOR_PLACEHOLDER_STRONG)
        painter.drawText(QRectF(0, cy - 16, self.width(), 26),
                         Qt.AlignHCenter | Qt.AlignVCenter, "等待图像输入")

        painter.setFont(body_font)
        painter.setPen(COLOR_PLACEHOLDER)
        painter.drawText(
            QRectF(0, cy + 14, self.width(), 24),
            Qt.AlignHCenter | Qt.AlignVCenter,
            "从左侧「加载图片」开始，或选择「视频跟踪」进行视频分析")

    def _paint_region(self, painter, scaled, dx, dy):
        """绘制区域顶点与多边形。"""
        if not self._points:
            return
        sx = scaled.width() / max(1, self._pixmap.width())
        sy = scaled.height() / max(1, self._pixmap.height())
        disp = [QPointF(dx + p.x() * sx, dy + p.y() * sy) for p in self._points]

        polygon = QPolygonF(disp)
        if len(disp) == 2:
            painter.setPen(QPen(COLOR_DRAW, 2))
            painter.drawLine(disp[0], disp[1])
        elif len(disp) >= 3:
            # 半透明填充，让区域范围一目了然
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(29, 111, 212, 38)))
            painter.drawPolygon(polygon)
            painter.setPen(QPen(COLOR_DRAW, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(polygon)

        # 顶点：白色描边 + 蓝色圆点，浅色画面/深色画面上都清晰
        for p in disp:
            painter.setPen(QPen(QColor("#ffffff"), 1.6))
            painter.setBrush(QBrush(COLOR_DRAW))
            painter.drawEllipse(p, 5.5, 5.5)
            painter.setPen(QPen(QColor("#ffffff"), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(p, 2.6, 2.6)

    def _paint_drawing_tip(self, painter):
        """绘制模式下左上角操作提示条。"""
        text = "左键添加顶点（≥3 个成区域）   |   右键清空   |   完成后点「完成区域」"
        font = QFont("Microsoft YaHei UI")
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.width(text) + 24
        h = 26
        box = QRectF(14, 14, min(w, self.width() - 28), h)
        painter.setPen(QPen(QColor(29, 111, 212, 90), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 236)))
        painter.drawRoundedRect(box, 8, 8)
        painter.setPen(QColor("#14539f"))
        painter.drawText(box.adjusted(12, 0, -12, 0),
                         Qt.AlignLeft | Qt.AlignVCenter, text)

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
