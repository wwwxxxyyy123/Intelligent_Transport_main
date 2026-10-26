"""实时交通统计图表（浅色主题）。

pyqtgraph 不走 Qt QSS，因此绘图区颜色/线型用 pyqtgraph 原生 API 配置，
其余文字层级（panelHead / chipLabel）仍由全局 QSS 驱动。
"""
from collections import deque

import pyqtgraph as pg
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.config import Config
from app.frontend.theme import (
    COLOR_BORDER, COLOR_CHART_FLOW, COLOR_CHART_GRID, COLOR_CHART_INSIDE,
    COLOR_CHART_TEXT, COLOR_TEXT_PRIMARY,
)

MAX_HISTORY_SECONDS = 120.0

# 浅色主题配色（与 theme.py 的强调色一致）
COLOR_AXIS = QColor(COLOR_CHART_GRID)
COLOR_AXIS_TEXT = QColor(COLOR_CHART_TEXT)
COLOR_FLOW = QColor(COLOR_CHART_FLOW)      # 蓝：流量
COLOR_INSIDE = QColor(COLOR_CHART_INSIDE)  # 琥珀：区域内数量
COLOR_LEGEND_BG = QColor(255, 255, 255, 235)
COLOR_LEGEND_BORDER = QColor(COLOR_BORDER)

pg.setConfigOptions(antialias=True)


class ChartPanel(QWidget):
    """实时交通统计曲线图表面板（流量 + 区域内数量）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.config = Config()
        self.sample_interval = self.config.get(
            'traffic', 'flow_window_seconds', default=1.0)
        self.max_points = max(10, min(500,
                                      int(MAX_HISTORY_SECONDS / self.sample_interval)))

        self._times = deque(maxlen=self.max_points)
        self._flow = deque(maxlen=self.max_points)
        self._inside = deque(maxlen=self.max_points)
        self._last_sample = -1.0

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        # 标题行：标题 + 时间范围标签
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("实时交通统计曲线")
        title.setObjectName("panelHead")
        head.addWidget(title)
        head.addStretch()
        window_chip = QLabel(f"最近 {int(MAX_HISTORY_SECONDS)} 秒")
        window_chip.setObjectName("chipLabel")
        head.addWidget(window_chip)
        layout.addLayout(head)

        # 绘图区（透明背景，跟随外层卡片渐变）
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.setClipToView(True)
        self.plot.setFrameStyle(0)
        self.plot.getPlotItem().hideButtons()

        self.plot.setLabel('left', '流量 / 区域内数量',
                           color=COLOR_CHART_TEXT, size='11px')
        self.plot.setLabel('bottom', '时间 (秒)',
                           color=COLOR_CHART_TEXT, size='11px')
        self.plot.showGrid(x=True, y=True, alpha=0.30)
        self.plot.getPlotItem().getViewBox().setBorder(
            QPen(QColor(COLOR_BORDER), 1))

        for axis in ('left', 'bottom'):
            ax = self.plot.getAxis(axis)
            ax.setPen(QPen(COLOR_AXIS))
            ax.setTextPen(QPen(COLOR_AXIS_TEXT))
            ax.setStyle(tickLength=-4)
            ax.setTickFont(pg.Qt.QtGui.QFont("Microsoft YaHei UI", 9))

        self.plot.setXRange(0, 30, padding=0.04)
        self.plot.setYRange(0, 10, padding=0.06)

        # 图例（浅色半透明）
        text_rgb = QColor(COLOR_TEXT_PRIMARY)
        self.legend = self.plot.addLegend(
            offset=(-6, 4),
            labelTextColor=(text_rgb.red(), text_rgb.green(), text_rgb.blue()),
            labelTextSize='10pt')
        self.legend.setPen(QPen(COLOR_LEGEND_BORDER))
        self.legend.setBrush(QBrush(COLOR_LEGEND_BG))

        # 流量曲线（蓝色 + 面积填充）
        self.flow_curve = self.plot.plot(
            pen=pg.mkPen(color=COLOR_FLOW, width=2.4),
            fillLevel=0.0,
            brush=pg.mkBrush(29, 111, 212, 26),
            symbol='o', symbolSize=5,
            symbolBrush=pg.mkBrush(COLOR_FLOW),
            symbolPen=pg.mkPen(QColor("#ffffff"), width=1.2),
            name='流量')
        # 区域内数量曲线（琥珀色，不填充，避免与流量填充叠加发灰）
        self.inside_curve = self.plot.plot(
            pen=pg.mkPen(color=COLOR_INSIDE, width=2.2),
            symbol='o', symbolSize=4,
            symbolBrush=pg.mkBrush(COLOR_INSIDE),
            symbolPen=pg.mkPen(QColor("#ffffff"), width=1.2),
            name='区域内数量')

        # 空态提示（有数据后隐藏）
        self._empty_text = pg.TextItem(
            "等待统计数据…", color=(136, 148, 171), anchor=(0.5, 0.5))
        self.plot.addItem(self._empty_text)
        self._empty_text.setPos(15, 5)

        layout.addWidget(self.plot, stretch=1)

    def update_stats(self, stats):
        ct = stats.get('current_time', 0.0)
        if self._last_sample < 0:
            self._last_sample = ct
            return
        if ct - self._last_sample < self.sample_interval:
            return
        self._last_sample = ct
        self._times.append(ct)
        self._flow.append(stats.get('flow_rate', 0))
        self._inside.append(stats.get('current_inside', 0))
        self._refresh()

    def _refresh(self):
        if not self._times:
            return
        self._empty_text.setVisible(False)
        t_max = self._times[-1]
        self.flow_curve.setData(list(self._times), list(self._flow))
        self.inside_curve.setData(list(self._times), list(self._inside))
        start = max(0.0, t_max - MAX_HISTORY_SECONDS)
        self.plot.setXRange(start, t_max + self.sample_interval, padding=0.04)
        vals = list(self._flow) + list(self._inside)
        y_max = max(max(vals) * 1.25, 10)
        self.plot.setYRange(0, y_max, padding=0.06)

    def reset(self):
        self._times.clear()
        self._flow.clear()
        self._inside.clear()
        self._last_sample = -1.0
        self.flow_curve.setData([], [])
        self.inside_curve.setData([], [])
        self.plot.setXRange(0, 30, padding=0.04)
        self.plot.setYRange(0, 10, padding=0.06)
        self._empty_text.setVisible(True)
        self._empty_text.setPos(15, 5)
