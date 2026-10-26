"""左侧功能面板：文件/图片/视频操作分组、类别图例与拥堵阈值设置。

视觉：所有颜色/边框由全局 QSS 驱动；按钮通过 btn_qss(kind) 区分主次与危险操作。
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.config import Config
from app.frontend.theme import (
    LEGEND_RING, btn_mini_qss, btn_qss, bgr_to_qss,
)


class ButtonPanel(QWidget):
    """左侧功能面板。"""

    load_clicked = pyqtSignal()
    infer_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    video_clicked = pyqtSignal()
    finish_region_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    congestion_threshold_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        # Minimum 策略避免被 Splitter 压缩到最小宽度以下
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.setMinimumWidth(232)

        self.config = Config()
        self._buttons = {}
        self._build_ui()
        self.set_state("idle")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(9)

        head = QLabel("功能菜单")
        head.setObjectName("panelHead")
        root.addWidget(head)

        # 图片分析
        root.addWidget(self._section_title("图片分析"))
        self._buttons["load"] = self._add_btn(
            root, "加载图片", self.load_clicked, "ghost")
        self._buttons["infer"] = self._add_btn(
            root, "图像推理", self.infer_clicked, "primary")
        self._buttons["clear"] = self._add_btn(
            root, "清空显示", self.clear_clicked, "ghost")
        root.addWidget(self._soft_divider())

        # 视频分析
        root.addWidget(self._section_title("视频分析"))
        self._buttons["video"] = self._add_btn(
            root, "视频追踪", self.video_clicked, "primary")
        self._buttons["finish"] = self._add_btn(
            root, "完成区域", self.finish_region_clicked, "success")
        self._buttons["stop"] = self._add_btn(
            root, "停止", self.stop_clicked, "danger")

        root.addWidget(self._divider())

        # 类别图例
        root.addWidget(self._section_title("类别图例"))
        legend_tile = QFrame()
        legend_tile.setObjectName("tile")
        self._legend_layout = QVBoxLayout(legend_tile)
        self._legend_layout.setContentsMargins(10, 8, 10, 8)
        self._legend_layout.setSpacing(7)
        self._legend_layout.addWidget(self._placeholder_row("等待模型加载…"))
        root.addWidget(legend_tile)

        root.addWidget(self._divider())

        # 参数设置：拥堵阈值
        root.addWidget(self._section_title("参数设置"))
        threshold_tile = QFrame()
        threshold_tile.setObjectName("tile")
        threshold_row = QHBoxLayout(threshold_tile)
        threshold_row.setContentsMargins(10, 7, 10, 7)
        threshold_row.setSpacing(6)

        threshold_label = QLabel("拥堵阈值")
        threshold_label.setObjectName("secondaryLabel")
        threshold_row.addWidget(threshold_label)
        threshold_row.addStretch(1)

        default_threshold = self.config.get('traffic', 'congestion_threshold', default=5)
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._threshold_spin.setRange(1, 999)
        self._threshold_spin.setValue(int(default_threshold))
        self._threshold_spin.setAlignment(Qt.AlignCenter)
        self._threshold_spin.setFixedWidth(52)
        self._threshold_spin.setToolTip("区域内目标数量大于该值时，视频区域显示为红色提示拥堵")
        self._threshold_spin.valueChanged.connect(self.congestion_threshold_changed.emit)

        self._threshold_minus = self._round_button("−")
        self._threshold_minus.setToolTip("减小拥堵阈值")
        self._threshold_minus.clicked.connect(self._threshold_spin.stepDown)
        self._threshold_plus = self._round_button("+")
        self._threshold_plus.setToolTip("增大拥堵阈值")
        self._threshold_plus.clicked.connect(self._threshold_spin.stepUp)

        threshold_row.addWidget(self._threshold_minus)
        threshold_row.addWidget(self._threshold_spin)
        threshold_row.addWidget(self._threshold_plus)
        root.addWidget(threshold_tile)

        hint = QLabel("畅通 ● 绿    拥堵 ● 红")
        hint.setObjectName("hintChip")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            hint.styleSheet() +
            "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 rgba(15, 155, 98, 0.16), stop:0.5 rgba(255, 255, 255, 0.0),"
            " stop:1 rgba(221, 75, 63, 0.16));")
        root.addWidget(hint)

        root.addStretch(1)
        info = QLabel("智能交通检测系统\n原型 v2.1")
        info.setObjectName("mutedLabel")
        info.setAlignment(Qt.AlignCenter)
        root.addWidget(info)

    # ---------- UI 辅助 ----------
    def _section_title(self, text):
        lb = QLabel(text)
        lb.setObjectName("sectionTitle")
        return lb

    def _divider(self):
        d = QFrame()
        d.setObjectName("divider")
        return d

    def _soft_divider(self):
        d = QFrame()
        d.setObjectName("dividerSoft")
        return d

    def _add_btn(self, layout, text, signal, kind="primary"):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setMinimumHeight(36)
        btn.setStyleSheet(btn_qss(kind))
        btn.clicked.connect(signal.emit)
        layout.addWidget(btn)
        return btn

    def _round_button(self, text):
        """圆形小按钮（用于拥堵阈值步进）。"""
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(26, 26)
        btn.setStyleSheet(btn_mini_qss())
        return btn

    @staticmethod
    def _placeholder_row(text):
        lb = QLabel(text)
        lb.setObjectName("mutedLabel")
        return lb

    # ---------- 图例 ----------
    def update_legend(self, class_colors):
        """重建图例，class_colors 为 [(class_name, bgr_color), ...]。"""
        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not class_colors:
            self._legend_layout.addWidget(self._placeholder_row("暂无可显示类别"))
            return

        for name, bgr in class_colors:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(9)
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background-color: {bgr_to_qss(bgr)}; "
                f"border: 1px solid {LEGEND_RING}; border-radius: 4px;")
            text = QLabel(str(name))
            text.setObjectName("secondaryLabel")
            row.addWidget(swatch)
            row.addWidget(text)
            row.addStretch()

            wrap = QWidget()
            wrap.setStyleSheet("background-color: transparent;")
            wrap.setLayout(row)
            self._legend_layout.addWidget(wrap)

    # ---------- 状态机 ----------
    def set_state(self, state):
        """按工作模式（idle/drawing/tracking）切换按钮可用状态。"""
        is_idle = state == "idle"
        is_drawing = state == "drawing"
        for key in ("load", "infer", "clear", "video"):
            self._buttons[key].setEnabled(is_idle)
        self._buttons["finish"].setEnabled(is_drawing)
        self._buttons["stop"].setEnabled(is_drawing or state == "tracking")

    def get_congestion_threshold(self):
        return self._threshold_spin.value()
