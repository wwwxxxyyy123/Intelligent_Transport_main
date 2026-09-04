"""全局主题：设计 Token + 全局 QSS + 共享控件样式。

业务组件不写局部颜色/边框类 QSS：
- 面板容器使用 objectName("card")，文字层级使用 panelHead/cardTitle/
  largeNumber/secondaryLabel 等 objectName，由全局 QSS 统一驱动
- 操作按钮统一使用 BTN_QSS（蓝底白字，与表格表头一致）
"""

# ---- 颜色 ----
COLOR_BG_PRIMARY   = "#f0f2f5"   # 页面底色
COLOR_BG_CARD      = "#ffffff"   # 卡片背景
COLOR_BG_HOVER     = "#f3f4f6"   # 悬停浅灰
COLOR_PRIMARY      = "#2563eb"   # 主色蓝（子标题/表头/选中态）
COLOR_PRIMARY_HV   = "#1d4ed8"
COLOR_TEXT_PRIMARY = "#1f2937"
COLOR_TEXT_SECOND  = "#6b7280"
COLOR_TEXT_MUTED   = "#9ca3af"
COLOR_TEXT_INVERT  = "#ffffff"
COLOR_BORDER       = "#e5e7eb"
COLOR_BORDER_SOFT  = "#f3f4f6"

# ---- 按钮配色（蓝底白字，与表头一致） ----
BTN_BG = "#2563eb"
BTN_HV = "#1d4ed8"
BTN_PD = "#1e40af"

# ---- 字号 ----
FONT_FAMILY     = "Microsoft YaHei UI"
FONT_SIZE_BASE  = 13   # 正文（按钮、表格、标签）
FONT_SIZE_LABEL = 13   # 次级标签
FONT_SIZE_NUM   = 18   # 统计数值
FONT_SIZE_TITLE = 15   # 卡片内子标题
FONT_SIZE_HEAD  = 16   # 面板大标题

# ---- 圆角/间距 ----
RADIUS_CARD  = 8
RADIUS_BTN   = 6
RADIUS_SMALL = 4
PAD_CARD     = 14
PAD_SECTION  = 8


def bgr_to_qss(bgr):
    """BGR 元组转 CSS rgb() 字符串（图例色块用）。"""
    b, g, r = bgr
    return f"rgb({r}, {g}, {b})"


# 统一按钮样式（直接 setStyleSheet 到具体按钮，避免属性选择器不生效问题）
BTN_QSS = f"""
QPushButton {{
    background-color: {BTN_BG};
    color: #ffffff;
    border: 1px solid {BTN_HV};
    border-radius: {RADIUS_BTN}px;
    font-weight: 600;
    padding: 7px 14px;
    min-height: 20px;
}}
QPushButton:hover {{ background-color: {BTN_HV}; }}
QPushButton:pressed {{ background-color: {BTN_PD}; }}
QPushButton:disabled {{
    background-color: {COLOR_BG_HOVER};
    color: {COLOR_TEXT_MUTED};
    border: 1px solid {COLOR_BORDER};
}}
"""


def build_global_qss():
    """构建应用全局样式表。"""
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

/* ============== 卡片容器 ============== */
QWidget#card, QFrame#card {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* ============== 文字层级 ============== */
QLabel#panelHead {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_HEAD}px;
    font-weight: 600;
    padding: 2px 0 6px 0;
}}
QLabel#cardTitle {{
    color: {COLOR_PRIMARY};
    font-size: {FONT_SIZE_TITLE}px;
    font-weight: 600;
    padding-bottom: 4px;
    border-bottom: 1px solid {COLOR_BORDER_SOFT};
}}
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

/* ============== 分隔线 ============== */
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

/* ============== SpinBox ============== */
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

/* ============== TabWidget ============== */
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

/* ============== TextBrowser（Markdown 渲染区） ============== */
QTextBrowser {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    padding: 8px;
    line-height: 1.6;
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

/* ============== 滚动条 ============== */
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

/* ============== 对话框 ============== */
QFileDialog, QMessageBox {{
    background-color: {COLOR_BG_PRIMARY};
}}
"""
