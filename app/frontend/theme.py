"""全局主题：设计 Token + 全局 QSS + 共享控件样式。

视觉风格：浅色「白天指挥台」（近白卡片 + 蓝色强调 + 浅灰分隔），
适合白天办公环境，长时间观看视频画面时对比更柔和。

业务组件不写局部颜色/边框类 QSS：
- 面板容器使用 objectName("card")，子卡片使用 objectName("tile")
- 文字层级使用 panelHead / sectionTitle / cardTitle / statValue / secondaryLabel
  等 objectName，由全局 QSS 统一驱动
- 按钮统一使用 btn_qss(kind)，按语义选择 primary / ghost / success / danger
"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap,
)

# ---- 颜色 ----
COLOR_BG_PRIMARY   = "#e8eef7"   # 页面底色（浅灰蓝）
COLOR_BG_CARD      = "#ffffff"   # 卡片背景
COLOR_BG_CARD_HI   = "#ffffff"   # 卡片渐变上沿 / 悬停
COLOR_BG_TILE      = "#f6f8fc"   # 卡片内子块背景
COLOR_BG_HOVER     = "#eaf1fb"   # 悬停
COLOR_BORDER       = "#dbe3f0"   # 常规描边
COLOR_BORDER_SOFT  = "#e9eff8"   # 弱描边
COLOR_TEXT_PRIMARY = "#17233a"   # 主文字
COLOR_TEXT_SECOND  = "#55617c"   # 次级文字
COLOR_TEXT_MUTED   = "#8894ab"   # 弱化文字
COLOR_TEXT_INVERT  = "#ffffff"   # 亮色文字（用于深色底）

COLOR_ACCENT       = "#1d6fd4"   # 主强调色（蓝）
COLOR_ACCENT_2     = "#2f8ae0"   # 辅助蓝
COLOR_ACCENT_DARK  = "#14539f"
COLOR_SUCCESS      = "#0f9b62"   # 畅通 / 完成
COLOR_WARN         = "#c47a08"   # 拥堵预警
COLOR_DANGER       = "#dd4b3f"   # 错误 / 停止
COLOR_INFO         = "#6d4fd0"   # 辅助信息

# ---- 图表 / 自绘画布配色（pyqtgraph 与 QPainter 不走 QSS）----
COLOR_CHART_FLOW    = "#1d6fd4"  # 流量曲线
COLOR_CHART_INSIDE  = "#d98c08"  # 区域内数量曲线
COLOR_CHART_GRID    = "#c9d4e4"  # 坐标轴与网格
COLOR_CHART_TEXT    = "#55617c"  # 坐标轴文字
COLOR_CANVAS_TOP    = "#f2f6fc"  # 图像画布（上）
COLOR_CANVAS_BOTTOM = "#e9eff8"  # 图像画布（下）
COLOR_DRAW          = "#1d6fd4"  # 区域绘制描边

# 兼容旧命名（其他模块可能引用）
COLOR_PRIMARY = COLOR_ACCENT
COLOR_PRIMARY_HV = COLOR_ACCENT_2

# ---- 字号 ----
FONT_FAMILY     = "Microsoft YaHei UI"
FONT_MONO       = "Bahnschrift"          # 数值字体（随 Windows 10+ 提供）
FONT_SIZE_BASE  = 13
FONT_SIZE_LABEL = 12
FONT_SIZE_NUM   = 26
FONT_SIZE_TITLE = 14
FONT_SIZE_HEAD  = 17

# ---- 圆角 / 间距 ----
RADIUS_CARD  = 14
RADIUS_TILE  = 12
RADIUS_BTN   = 10
RADIUS_SMALL = 8
PAD_CARD     = 16
PAD_SECTION  = 10


def bgr_to_qss(bgr):
    """BGR 元组转 CSS rgb() 字符串（图例色块用）。"""
    b, g, r = bgr
    return f"rgb({r}, {g}, {b})"


# 图例色块描边（中性浅色，避免干扰真实类别色）
LEGEND_RING = "#c9d4e4"


# ------------------------------------------------------------------
# 按钮：按语义分四种
# ------------------------------------------------------------------
def btn_qss(kind="primary"):
    """生成按钮样式表。

    kind: primary（主操作）/ ghost（次要）/ success（完成）/ danger（停止）。
    """
    if kind == "ghost":
        bg, bg_hv, bg_pd = "#ffffff", COLOR_BG_HOVER, "#e4edf9"
        fg = COLOR_TEXT_SECOND
        border = COLOR_BORDER
        hover_fg = COLOR_TEXT_PRIMARY
    elif kind == "success":
        bg, bg_hv, bg_pd = "#0f9b62", "#12ab6d", "#0b7c4e"
        fg = "#ffffff"
        border = "#0f9b62"
        hover_fg = "#ffffff"
    elif kind == "danger":
        bg = "rgba(221, 75, 63, 0.08)"
        bg_hv = "rgba(221, 75, 63, 0.16)"
        bg_pd = "rgba(221, 75, 63, 0.24)"
        fg = "#c0392f"
        border = "rgba(221, 75, 63, 0.35)"
        hover_fg = "#a82d24"
    else:  # primary
        bg, bg_hv, bg_pd = "#1d6fd4", "#2f8ae0", "#14539f"
        fg = "#ffffff"
        border = "#1d6fd4"
        hover_fg = "#ffffff"

    return f"""
QPushButton {{
    background-color: {bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: {RADIUS_BTN}px;
    font-weight: 600;
    padding: 8px 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {bg_hv};
    color: {hover_fg};
}}
QPushButton:pressed {{ background-color: {bg_pd}; }}
QPushButton:disabled {{
    background-color: {COLOR_BG_TILE};
    color: {COLOR_TEXT_MUTED};
    border: 1px solid {COLOR_BORDER_SOFT};
}}
"""


BTN_QSS = btn_qss("primary")          # 兼容旧引用
BTN_GHOST_QSS = btn_qss("ghost")
BTN_SUCCESS_QSS = btn_qss("success")
BTN_DANGER_QSS = btn_qss("danger")


def btn_mini_qss():
    """紧凑圆形小按钮（数值步进器的 +/-）。"""
    return f"""
QPushButton {{
    background-color: {COLOR_BG_TILE};
    color: {COLOR_TEXT_SECOND};
    border: 1px solid {COLOR_BORDER};
    border-radius: 9px;
    font-size: 15px;
    font-weight: 700;
    padding: 0px;
}}
QPushButton:hover {{
    background-color: rgba(29, 111, 212, 0.10);
    color: {COLOR_ACCENT};
    border-color: rgba(29, 111, 212, 0.45);
}}
QPushButton:pressed {{ background-color: rgba(29, 111, 212, 0.20); }}
QPushButton:disabled {{
    background-color: {COLOR_BG_TILE};
    color: {COLOR_TEXT_MUTED};
    border-color: {COLOR_BORDER_SOFT};
}}
"""


# ------------------------------------------------------------------
# 应用图标：用 QPainter 现画（不引入图片资源）
# ------------------------------------------------------------------
def make_app_icon(size=64):
    """绘制应用图标：圆角底 + 交通灯三色点 + 车道线。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4aa3f0"))
    grad.setColorAt(1.0, QColor("#1d6fd4"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.24, size * 0.24)

    # 交通灯外壳
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawRoundedRect(QRectF(size * 0.30, size * 0.14, size * 0.40, size * 0.72),
                      size * 0.10, size * 0.10)

    # 三个灯
    for i, col in enumerate(("#e0453a", "#e8a712", "#12a66a")):
        p.setBrush(QColor(col))
        cy = size * (0.28 + i * 0.22)
        p.drawEllipse(QPointF(size * 0.50, cy), size * 0.075, size * 0.075)

    p.end()
    return QIcon(pm)


# ------------------------------------------------------------------
# 全局 QSS
# ------------------------------------------------------------------
def build_global_qss():
    """构建应用全局样式表。"""
    return f"""
/* ============== 全局基础 ============== */
* {{
    font-family: "{FONT_FAMILY}", "微软雅黑", "Segoe UI";
    font-size: {FONT_SIZE_BASE}px;
    color: {COLOR_TEXT_PRIMARY};
    outline: none;
}}
QWidget {{
    background-color: {COLOR_BG_PRIMARY};
}}
QLabel, QCheckBox, QRadioButton {{
    background-color: transparent;
}}
QMainWindow {{
    background-color: {COLOR_BG_PRIMARY};
}}

/* ============== 顶栏 ============== */
QWidget#header {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffffff, stop:0.55 #fbfdff, stop:1 #f4f9ff);
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QLabel#appTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 19px;
    font-weight: 700;
}}
QLabel#appSubtitle {{
    color: {COLOR_TEXT_MUTED};
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#badge {{
    color: {COLOR_ACCENT_DARK};
    background-color: rgba(29, 111, 212, 0.08);
    border: 1px solid rgba(29, 111, 212, 0.26);
    border-radius: 11px;
    padding: 4px 12px;
    font-size: {FONT_SIZE_LABEL}px;
    font-weight: 600;
}}
QLabel#badgeOk {{
    color: #0b7c4e;
    background-color: rgba(15, 155, 98, 0.09);
    border: 1px solid rgba(15, 155, 98, 0.28);
    border-radius: 11px;
    padding: 4px 12px;
    font-size: {FONT_SIZE_LABEL}px;
    font-weight: 600;
}}
QLabel#badgeBusy {{
    color: #a0640a;
    background-color: rgba(196, 122, 8, 0.11);
    border: 1px solid rgba(196, 122, 8, 0.30);
    border-radius: 11px;
    padding: 4px 12px;
    font-size: {FONT_SIZE_LABEL}px;
    font-weight: 600;
}}

/* ============== 卡片容器 ============== */
QWidget#card, QFrame#card {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLOR_BG_CARD_HI}, stop:0.14 #fdfeff, stop:1 {COLOR_BG_CARD});
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* 卡片内子块 */
QFrame#tile {{
    background-color: {COLOR_BG_TILE};
    border: 1px solid {COLOR_BORDER_SOFT};
    border-radius: {RADIUS_TILE}px;
}}

/* ============== 文字层级 ============== */
QLabel#panelHead {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_HEAD}px;
    font-weight: 700;
    padding: 0 0 2px 0;
}}
QLabel#sectionTitle {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_LABEL}px;
    font-weight: 700;
    padding: 2px 0 2px 9px;
    border-left: 3px solid {COLOR_ACCENT};
}}
QLabel#cardTitle {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_TITLE}px;
    font-weight: 700;
}}
QLabel#secondaryLabel {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#mutedLabel {{
    color: {COLOR_TEXT_MUTED};
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#statValue {{
    color: {COLOR_ACCENT};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: {FONT_SIZE_NUM}px;
    font-weight: 700;
}}
QLabel#statValueOk {{
    color: {COLOR_SUCCESS};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: {FONT_SIZE_NUM}px;
    font-weight: 700;
}}
QLabel#statValueWarn {{
    color: {COLOR_WARN};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: {FONT_SIZE_NUM}px;
    font-weight: 700;
}}
QLabel#statValueInfo {{
    color: {COLOR_INFO};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: {FONT_SIZE_NUM}px;
    font-weight: 700;
}}
QLabel#largeNumber {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: 17px;
    font-weight: 700;
}}
QLabel#hintChip {{
    color: {COLOR_TEXT_SECOND};
    background-color: {COLOR_BG_TILE};
    border: 1px solid {COLOR_BORDER_SOFT};
    border-radius: {RADIUS_SMALL}px;
    padding: 6px 8px;
    font-size: {FONT_SIZE_LABEL}px;
}}
QLabel#monoValue {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: 14px;
    font-weight: 600;
}}
QLabel#emptyHint {{
    color: {COLOR_TEXT_MUTED};
    font-size: {FONT_SIZE_LABEL}px;
    padding: 10px 4px;
}}
QLabel#chipLabel {{
    color: {COLOR_ACCENT_DARK};
    background-color: rgba(29, 111, 212, 0.07);
    border: 1px solid rgba(29, 111, 212, 0.18);
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 600;
}}

/* ============== 分隔线 ============== */
QFrame#divider {{
    background-color: {COLOR_BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QFrame#dividerSoft {{
    background-color: {COLOR_BORDER_SOFT};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* ============== SpinBox ============== */
QSpinBox {{
    background-color: #ffffff;
    color: {COLOR_ACCENT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_SMALL}px;
    font-family: "{FONT_MONO}", "Consolas", "{FONT_FAMILY}";
    font-size: 15px;
    font-weight: 700;
    padding: 4px 8px;
    selection-background-color: rgba(29, 111, 212, 0.22);
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QSpinBox:focus {{ border: 1px solid {COLOR_ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 16px;
    background-color: transparent;
    border: none;
    border-left: 1px solid {COLOR_BORDER_SOFT};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: rgba(29, 111, 212, 0.10);
}}

/* ============== 进度条 ============== */
QProgressBar {{
    background-color: #e6edf8;
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: {COLOR_TEXT_SECOND};
    font-size: 11px;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLOR_ACCENT_2}, stop:1 {COLOR_ACCENT});
}}

/* ============== 表格 ============== */
QTableWidget {{
    background-color: #ffffff;
    alternate-background-color: #f8fafd;
    color: {COLOR_TEXT_PRIMARY};
    gridline-color: transparent;
    border: 1px solid {COLOR_BORDER_SOFT};
    border-radius: {RADIUS_SMALL}px;
    selection-background-color: rgba(29, 111, 212, 0.13);
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QTableWidget::item {{
    padding: 4px 6px;
    border-bottom: 1px solid {COLOR_BORDER_SOFT};
}}
QHeaderView::section {{
    background-color: #f2f6fc;
    color: {COLOR_TEXT_SECOND};
    font-weight: 600;
    font-size: {FONT_SIZE_LABEL}px;
    padding: 7px 8px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
}}
QTableCornerButton::section {{ background-color: #f2f6fc; border: none; }}

/* ============== TabWidget（胶囊式） ============== */
QTabWidget::pane {{
    border: none;
    background-color: transparent;
    top: 6px;
}}
QTabBar {{ background-color: transparent; }}
QTabBar::tab {{
    background-color: {COLOR_BG_TILE};
    color: {COLOR_TEXT_SECOND};
    padding: 7px 18px;
    border: 1px solid {COLOR_BORDER_SOFT};
    border-radius: 14px;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 4px;
}}
QTabBar::tab:hover {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: {COLOR_BG_HOVER};
}}
QTabBar::tab:selected {{
    background-color: rgba(29, 111, 212, 0.10);
    color: {COLOR_ACCENT_DARK};
    border: 1px solid rgba(29, 111, 212, 0.32);
}}
QTabBar::tab:disabled {{ color: {COLOR_TEXT_MUTED}; }}

/* ============== TextBrowser（Markdown 渲染区） ============== */
QTextBrowser {{
    background-color: transparent;
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    padding: 6px 8px;
    selection-background-color: rgba(29, 111, 212, 0.16);
}}

/* ============== Splitter ============== */
QSplitter {{ background-color: transparent; }}
QSplitter::handle:horizontal, QSplitter::handle:vertical {{
    background-color: transparent;
    width: 8px;
    height: 8px;
}}
QSplitter::handle:hover {{
    background-color: rgba(29, 111, 212, 0.26);
    border-radius: 3px;
}}

/* ============== 状态栏 ============== */
QStatusBar {{
    background-color: #ffffff;
    color: {COLOR_TEXT_SECOND};
    border-top: 1px solid {COLOR_BORDER};
    font-size: {FONT_SIZE_LABEL}px;
    padding: 2px 6px;
}}
QStatusBar QLabel {{
    color: {COLOR_TEXT_SECOND};
    font-size: {FONT_SIZE_LABEL}px;
    padding: 0 12px;
}}
QStatusBar::item {{ border: none; }}

/* ============== 滚动条 ============== */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #c9d4e4;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #aab8cd; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #c9d4e4;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #aab8cd; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ============== Tooltip ============== */
QToolTip {{
    background-color: #ffffff;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    padding: 6px 10px;
    border-radius: {RADIUS_SMALL}px;
    font-size: {FONT_SIZE_LABEL}px;
}}

/* ============== 对话框 ============== */
QFileDialog, QMessageBox {{
    background-color: {COLOR_BG_CARD};
}}
QMessageBox QLabel {{ color: {COLOR_TEXT_PRIMARY}; background-color: transparent; }}
QMessageBox QPushButton {{
    background-color: {COLOR_BG_TILE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_SMALL}px;
    padding: 6px 18px;
    min-width: 64px;
    font-weight: 600;
}}
QMessageBox QPushButton:hover {{
    background-color: {COLOR_BG_HOVER};
    border-color: {COLOR_ACCENT};
}}
"""
