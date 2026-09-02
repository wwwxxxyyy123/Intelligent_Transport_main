"""左侧功能面板（objectName 化，无局部颜色/边框 QSS，视觉由全局设计 Token 驱动）。

面板结构（纵向堆叠）：
    [功能菜单] 大标题
    文件操作 分组（清空显示）
    图片分析 分组（加载图片 / 图像推理）
    视频分析 分组（视频追踪 / 完成区域 / 停止）
    —— 分隔线 ——
    [类别图例] 分组
    —— 分隔线 ——
    [参数设置] 分组：拥堵阈值 + 状态提示
    stretch
    版本信息

对外暴露 pyqtSignal，由主窗口连接。按钮颜色角色通过 btnRole 属性区分。
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.config import Config


# 统一按钮样式（与 QTableWidget 表头配色一致：#2563eb 蓝底白字）
_BTN_QSS = """
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    font-weight: 600;
    padding: 7px 14px;
    min-height: 20px;
}
QPushButton:hover { background-color: #1d4ed8; }
QPushButton:pressed { background-color: #1e40af; }
QPushButton:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border: 1px solid #e5e7eb;
}
"""


def _bgr_to_qss(bgr):
    """BGR 元组转 CSS rgb 字符串（仅用于图例色块，不影响整体风格）。"""
    b, g, r = bgr
    return f"rgb({r}, {g}, {b})"


class ButtonPanel(QWidget):
    """左侧功能面板（按业务分组的现代风格）。"""

    load_clicked = pyqtSignal()
    infer_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    video_clicked = pyqtSignal()
    finish_region_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    congestion_threshold_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 卡片化容器（objectName: card → 全局 QSS 负责圆角白底）
        self.setObjectName("card")
        # 用 Minimum 让 Splitter 分配时不要挤压到比最小宽度更窄
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.setMinimumWidth(220)

        self.config = Config()
        self._buttons = {}
        self._build_ui()
        self.set_state("idle")

    # ---------- UI 构建 ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 面板大标题
        head = QLabel("功能菜单")
        head.setObjectName("panelHead")
        root.addWidget(head)

        # 分组 1：文件操作
        root.addWidget(self._section_title("文件操作"))
        self._buttons["clear"] = self._add_btn(root, "清空显示", "primary", self.clear_clicked)

        root.addWidget(self._soft_divider())

        # 分组 2：图片分析
        root.addWidget(self._section_title("图片分析"))
        self._buttons["load"] = self._add_btn(root, "加载图片", "primary", self.load_clicked)
        self._buttons["infer"] = self._add_btn(root, "图像推理", "primary", self.infer_clicked)

        root.addWidget(self._soft_divider())

        # 分组 3：视频分析
        root.addWidget(self._section_title("视频分析"))
        self._buttons["video"] = self._add_btn(root, "视频追踪", "primary", self.video_clicked)
        self._buttons["finish"] = self._add_btn(root, "完成区域", "primary", self.finish_region_clicked)
        self._buttons["stop"] = self._add_btn(root, "停止", "primary", self.stop_clicked)

        root.addWidget(self._divider())

        # 分组 4：类别图例
        legend_head = self._section_title("类别图例")
        root.addWidget(legend_head)
        self._legend_container = QWidget()
        self._legend_container.setStyleSheet("background-color: transparent;")
        self._legend_layout = QVBoxLayout(self._legend_container)
        self._legend_layout.setContentsMargins(4, 0, 0, 0)
        self._legend_layout.setSpacing(6)
        root.addWidget(self._legend_container)

        root.addWidget(self._divider())

        # 分组 5：参数设置 —— 拥堵阈值
        root.addWidget(self._section_title("参数设置"))

        th_row = QHBoxLayout()
        th_row.setSpacing(8)
        th_label = QLabel("拥堵阈值")
        th_label.setObjectName("secondaryLabel")
        th_row.addWidget(th_label)

        default_threshold = self.config.get(
            'traffic', 'congestion_threshold', default=5)
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(1, 999)
        self._threshold_spin.setValue(int(default_threshold))
        self._threshold_spin.setToolTip(
            "区域内目标数量大于该值时，视频区域显示为红色提示拥堵")
        self._threshold_spin.valueChanged.connect(
            self.congestion_threshold_changed.emit)
        th_row.addWidget(self._threshold_spin)
        th_row.addStretch()
        root.addLayout(th_row)

        # 状态色块提示
        hint = QLabel("  畅通（绿）    拥堵（红）")
        hint.setObjectName("secondaryLabel")
        hint.setStyleSheet(
            hint.styleSheet() +
            "padding: 6px; border-radius: 4px;"
            "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #d1fae5, stop:0.5 transparent, stop:1 #fee2e2);")
        root.addWidget(hint)

        # 底部 stretch + 版本信息
        root.addStretch()
        info = QLabel("智能交通检测系统\n原型 v2.1")
        info.setObjectName("mutedLabel")
        info.setAlignment(Qt.AlignCenter)
        root.addWidget(info)

    # ---------- 辅助：子标题/分割线/按钮工厂 ----------
    def _section_title(self, text):
        lb = QLabel(text)
        lb.setObjectName("cardTitle")
        return lb

    def _divider(self):
        d = QFrame()
        d.setObjectName("divider")
        return d

    def _soft_divider(self):
        d = QFrame()
        d.setObjectName("dividerSoft")
        return d

    def _add_btn(self, root_layout, text, role, signal):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setMinimumHeight(34)
        btn.setStyleSheet(_BTN_QSS)
        btn.clicked.connect(signal.emit)
        root_layout.addWidget(btn)
        return btn

    # ---------- 图例动态填充 ----------
    def update_legend(self, class_colors):
        """更新图例：class_colors 为 [(class_name, bgr_color), ...]。"""
        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for name, bgr in class_colors:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            swatch = QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                f"background-color: {_bgr_to_qss(bgr)}; "
                f"border: 1px solid #d1d5db; border-radius: 3px;")
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
        """按工作模式切换按钮可用状态。"""
        is_idle = (state == "idle")
        is_drawing = (state == "drawing")
        is_tracking = (state == "tracking")
        self._buttons["load"].setEnabled(is_idle)
        self._buttons["infer"].setEnabled(is_idle)
        self._buttons["clear"].setEnabled(is_idle)
        self._buttons["video"].setEnabled(is_idle)
        self._buttons["finish"].setEnabled(is_drawing)
        # 停止键：drawing 或 tracking 时可用
        self._buttons["stop"].setEnabled(is_drawing or is_tracking)

    def get_congestion_threshold(self):
        return self._threshold_spin.value()
