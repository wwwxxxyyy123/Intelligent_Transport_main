"""程序入口：设置 DPI 与全局主题 → 预加载模型 → 启动 PyQt5 应用。

模型加载（ONNX session 创建 + CUDA 初始化）耗时较长（5-10s），
移到窗口显示之前执行，避免首次检测时卡顿。加载过程中显示加载窗口。

样式体系集中在此文件：
- 全局字体（微软雅黑 13px）
- 高 DPI 属性（防止文字被压扁/裁切）
- 全局 QSS 设计 Token（颜色/间距/圆角/交互态）
- 所有组件视觉风格统一由 objectName / class 选择器驱动，
  业务组件里不再写局部颜色/padding 相关的 setStyleSheet。

运行方式（在项目根目录下）:
    python main.py
"""
import sys
import time

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from app.config import Config


# ================================================================
# 设计 Design Token（颜色体系、字号、间距、圆角）
# ================================================================
# 主色板（清新的现代蓝绿浅灰组合）
COLOR_BG_PRIMARY   = "#f0f2f5"   # 全局背景（页面底色）
COLOR_BG_CARD      = "#ffffff"   # 卡片/面板背景
COLOR_BG_HOVER     = "#f3f4f6"   # 悬停浅灰
COLOR_PRIMARY      = "#2563eb"   # 主按钮蓝（清醒不刺眼）
COLOR_PRIMARY_HV   = "#1d4ed8"   # 蓝-悬停
COLOR_PRIMARY_PD   = "#1e40af"   # 蓝-按下
COLOR_ACCENT       = "#059669"   # 强调绿（成功、开始类）
COLOR_ACCENT_HV    = "#047857"
COLOR_WARN         = "#d97706"   # 橙（AI分析类）
COLOR_WARN_HV      = "#b45309"
COLOR_DANGER       = "#dc2626"   # 红（停止类）
COLOR_DANGER_HV    = "#b91c1c"
COLOR_TEXT_PRIMARY = "#1f2937"   # 主文字（深蓝灰）
COLOR_TEXT_SECOND  = "#6b7280"   # 次文字
COLOR_TEXT_MUTED   = "#9ca3af"   # 辅助/禁用文字
COLOR_TEXT_INVERT  = "#ffffff"   # 反色文字（按钮上）
COLOR_BORDER       = "#e5e7eb"   # 常规分隔线/边框
COLOR_BORDER_SOFT  = "#f3f4f6"   # 卡片内部软分割

# 按钮统一配色（深海蓝 + 柔奶白）
COLOR_BTN_BG       = "#1e3a5f"   # 深海蓝（按钮统一底色）
COLOR_BTN_HV       = "#15293e"   # 深海蓝-悬停
COLOR_BTN_PD       = "#0f1f30"   # 深海蓝-按下
COLOR_BTN_TEXT     = "#f5f0e6"   # 柔奶白（按钮文字）

# 字号体系
FONT_FAMILY     = "Microsoft YaHei UI"   # Windows 原生清晰无锯齿
FONT_SIZE_BASE  = 13   # 正文（按钮、表格、标签）
FONT_SIZE_LABEL = 13   # 次级标签
FONT_SIZE_NUM   = 18   # 统计数值（加大）
FONT_SIZE_TITLE = 15   # 卡片内子标题
FONT_SIZE_HEAD  = 16   # 面板大标题

# 圆角/间距基准
RADIUS_CARD     = 8    # 卡片面板圆角
RADIUS_BTN      = 6    # 按钮圆角
RADIUS_SMALL    = 4    # 输入/提示小圆角
PAD_CARD        = 14   # 卡片内边距
PAD_SECTION     = 8    # 组件间垂直间距


def _build_global_qss():
    """构建全局样式表。按业务面板 objectName 分组，集中管理视觉风格。"""
    return f"""
/* ============== 全局基础 ============== */
* {{
    font-family: "{FONT_FAMILY}", "微软雅黑", "Segoe UI";
    font-size: {FONT_SIZE_BASE}px;
    color: {COLOR_TEXT_PRIMARY};
}}
QWidget {{
    background-color: {COLOR_BG_PRIMARY};
}}

/* ============== 卡片面板容器（objectName: card） ============== */
QWidget#card {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#card {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* 面板大标题（objectName: panelHead） */
QLabel#panelHead {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_HEAD}px;
    font-weight: 600;
    padding: 2px 0 6px 0;
}}
/* 卡片内子标题（objectName: cardTitle） */
QLabel#cardTitle {{
    color: {COLOR_PRIMARY};
    font-size: {FONT_SIZE_TITLE}px;
    font-weight: 600;
    padding-bottom: 4px;
    border-bottom: 1px solid {COLOR_BORDER_SOFT};
}}
/* 次级标签 */
QLabel#secondaryLabel {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#mutedLabel {{
    color: {COLOR_TEXT_MUTED};
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#largeNumber {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_NUM}px;
    font-weight: 700;
}}

/* 分隔线（objectName: divider） */
QFrame#divider {{
    background-color: {COLOR_BORDER};
    max-height: 1px;
    min-height: 1px;
}}
QFrame#dividerSoft {{
    background-color: {COLOR_BORDER_SOFT};
    max-height: 1px;
    min-height: 1px;
}}

/* ============== 主按钮样式（深海蓝统一配色） ============== */
QPushButton[btnRole="primary"],
QPushButton[btnRole="accent"],
QPushButton[btnRole="warn"],
QPushButton[btnRole="danger"] {{
    background-color: {COLOR_BTN_BG};
    color: {COLOR_BTN_TEXT};
    border: 1px solid {COLOR_BTN_HV};
    border-radius: {RADIUS_BTN}px;
    font-weight: 600;
    padding: 7px 14px;
    min-height: 20px;
}}
QPushButton[btnRole="primary"]:hover,
QPushButton[btnRole="accent"]:hover,
QPushButton[btnRole="warn"]:hover,
QPushButton[btnRole="danger"]:hover {{
    background-color: {COLOR_BTN_HV};
}}
QPushButton[btnRole="primary"]:pressed,
QPushButton[btnRole="accent"]:pressed,
QPushButton[btnRole="warn"]:pressed,
QPushButton[btnRole="danger"]:pressed {{
    background-color: {COLOR_BTN_PD};
}}

QPushButton:disabled {{
    background-color: {COLOR_BG_HOVER} !important;
    color: {COLOR_TEXT_MUTED} !important;
    border: 1px solid {COLOR_BORDER} !important;
}}

/* ============== SpinBox（拥堵阈值） ============== */
QSpinBox {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_SMALL}px;
    font-weight: 600;
    padding: 4px 6px;
}}
QSpinBox:focus {{
    border: 1px solid {COLOR_PRIMARY};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {COLOR_BG_HOVER};
    width: 16px;
    border: none;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {COLOR_BORDER};
}}

/* ============== 表格 ============== */
QTableWidget {{
    background-color: {COLOR_BG_CARD};
    alternate-background-color: {COLOR_BG_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
    gridline-color: {COLOR_BORDER_SOFT};
    border: none;
    selection-background-color: {COLOR_PRIMARY};
    selection-color: {COLOR_TEXT_INVERT};
}}
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_TEXT_INVERT};
    font-weight: 600;
    font-size: {FONT_SIZE_BASE}px;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {COLOR_PRIMARY_HV};
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ============== TabWidget（LLM 面板标签页） ============== */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
    background-color: {COLOR_BG_CARD};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {COLOR_BG_HOVER};
    color: {COLOR_TEXT_PRIMARY};
    padding: 6px 18px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-top-left-radius: {RADIUS_SMALL}px;
    border-top-right-radius: {RADIUS_SMALL}px;
    font-weight: 500;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_TEXT_INVERT};
    border-color: {COLOR_PRIMARY_HV};
}}

/* ============== TextBrowser（AI Markdown 渲染） ============== */
QTextBrowser {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    padding: 8px;
    line-height: 1.6;
}}
QTextBrowser QScrollBar:vertical,
QTextEdit QScrollBar:vertical,
QTableWidget QScrollBar:vertical {{
    background: {COLOR_BG_PRIMARY};
    width: 10px;
    border: none;
}}

/* ============== Splitter ============== */
QSplitter {{
    background-color: transparent;
}}
QSplitter::handle:horizontal,
QSplitter::handle:vertical {{
    background-color: transparent;
    width: 3px;
    height: 3px;
}}
QSplitter::handle:hover {{
    background-color: {COLOR_PRIMARY};
}}

/* ============== 菜单/菜单栏（主窗口 QMenuBar） ============== */
QMenuBar {{
    background-color: {COLOR_BG_CARD};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 2px 6px;
    font-weight: 500;
}}
QMenuBar::item {{
    padding: 6px 14px;
    background: transparent;
    border-radius: {RADIUS_SMALL}px;
}}
QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_TEXT_INVERT};
}}
QMenu {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_PRIMARY};
    padding: 4px 0;
    border-radius: {RADIUS_SMALL}px;
}}
QMenu::item {{
    padding: 7px 28px 7px 24px;
    font-weight: 500;
}}
QMenu::item:selected {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_TEXT_INVERT};
}}
QMenu::separator {{
    height: 1px;
    background-color: {COLOR_BORDER};
    margin: 4px 8px;
}}

/* ============== 状态栏 ============== */
QStatusBar {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_SECOND};
    border-top: 1px solid {COLOR_BORDER};
    font-size: {FONT_SIZE_LABEL}px;
}}
QStatusBar QLabel {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_LABEL}px;
    padding: 0 12px;
}}

/* ============== 滚动条（全局） ============== */
QScrollBar:vertical {{
    background: {COLOR_BG_PRIMARY};
    width: 10px;
    border: none;
    margin: 2px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: #c9ccd1;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #9ca3af; }}
QScrollBar:horizontal {{
    background: {COLOR_BG_PRIMARY};
    height: 10px;
    border: none;
    margin: 2px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: #c9ccd1;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #9ca3af; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    width: 0;
    height: 0;
}}

/* ============== Tooltip ============== */
QToolTip {{
    background-color: {COLOR_TEXT_PRIMARY};
    color: {COLOR_TEXT_INVERT};
    border: none;
    padding: 6px 10px;
    border-radius: {RADIUS_SMALL}px;
    font-size: {FONT_SIZE_LABEL}px;
}}

/* ============== FileDialog / MessageBox 通用（保持系统原生）============== */
QFileDialog, QMessageBox {{
    background-color: {COLOR_BG_PRIMARY};
}}
"""


# ================================================================
# 加载窗口（样式复用全局 QSS，不单独写 setStyleSheet）
# ================================================================
class LoadingWindow(QWidget):
    """启动加载进度窗口（无局部 QSS，视觉由全局 QSS 接管）。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("加载中")
        self.setFixedSize(400, 180)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint)
        self.setObjectName("card")   # 启用卡片圆角与白底

        outer = QVBoxLayout(self)
        outer.setContentsMargins(PAD_CARD, PAD_CARD, PAD_CARD, PAD_CARD)
        outer.setSpacing(PAD_SECTION)

        title = QLabel("智能交通检测系统")
        title.setObjectName("panelHead")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        self._label = QLabel("正在初始化环境...")
        self._label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # 不确定进度
        self._progress.setTextVisible(True)
        self._progress.setFormat("加载中…")
        outer.addWidget(self._progress)

        self._tip = QLabel("首次加载需几秒，请稍候")
        self._tip.setObjectName("mutedLabel")
        self._tip.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._tip)

    def set_status(self, text):
        self._label.setText(text)
        QApplication.processEvents()


# ================================================================
# main 入口
# ================================================================
def main():
    # ------- 1) 高 DPI 与字体设置 —— 必须在任何 QWidget 创建之前 -------
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # 全局字体统一（微软雅黑 13px，避免 DPI 差异下文字裁切）
    base_font = QFont(FONT_FAMILY)
    base_font.setPointSize(FONT_SIZE_BASE)
    base_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(base_font)

    # 应用全局 QSS 主题（设计 Token 样式体系）
    app.setStyleSheet(_build_global_qss())

    # ------- 2) 显示加载窗口 -------
    loading = LoadingWindow()
    loading.show()
    app.processEvents()

    # ------- 3) 加载配置 -------
    loading.set_status("正在加载配置...")
    Config()

    # ------- 4) 预加载 Detector（ONNX session + CUDA 初始化 + dummy 推理预热） -------
    from app.backend.detector import Detector
    loading.set_status("正在加载检测模型（首次加载约需几秒）...")
    t0 = time.time()
    detector = None
    error_msg = None
    try:
        detector = Detector()
        import numpy as np
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        detector.model.predict(source=dummy, imgsz=detector.image_size,
                              conf=detector.conf, iou=detector.iou,
                              save=False, verbose=False)
        elapsed = time.time() - t0
        print(f"[加载] 模型预热完成，耗时 {elapsed:.1f}s")
    except Exception as e:
        error_msg = f"模型加载失败：{e}"

    # ------- 5) 关闭加载窗口 -------
    loading.close()
    QApplication.processEvents()

    # ------- 6) 加载失败则弹窗并退出 -------
    if error_msg:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(None, "启动失败", error_msg)
        sys.exit(1)

    # ------- 7) 创建主窗口并显示 -------
    from app.frontend.main_window import MainWindow
    window = MainWindow(detector=detector)
    window.show()

    # ------- 8) 进入事件循环 -------
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
