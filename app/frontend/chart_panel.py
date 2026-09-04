"""实时交通统计图表（objectName 化，无局部颜色/边框 QSS）。

pyqtgraph 的亮主题设置（setBackground / pen / label）保留在组件内，
因为 pyqtgraph 不走 Qt QSS，需要独立 API。"""
from collections import deque

import pyqtgraph as pg
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.config import Config

MAX_HISTORY_SECONDS = 120.0


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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        title = QLabel("实时交通统计曲线")
        title.setObjectName("panelHead")
        layout.addWidget(title)

        # pyqtgraph PlotWidget（亮主题）
        self.plot = pg.PlotWidget()
        self.plot.setBackground('#ffffff')
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.setClipToView(True)
        self.plot.setFrameStyle(0)   # 不画 Qt 边框（外层 card 已负责）
        # 坐标轴
        self.plot.setLabel('left', '流量/区域内数量', color='#1f2937', size='12px')
        self.plot.setLabel('bottom', '时间 (秒)', color='#1f2937', size='12px')
        self.plot.showGrid(x=True, y=True, alpha=0.25)

        for axis in ('left', 'bottom'):
            ax = self.plot.getAxis(axis)
            ax.setPen(QPen(QColor(200, 200, 200)))
            ax.setTextPen(QPen(QColor(31, 41, 55)))
            ax.setTickFont(pg.Qt.QtGui.QFont("Microsoft YaHei UI", 10))

        self.plot.setXRange(0, 30, padding=0.05)
        self.plot.setYRange(0, 10, padding=0.1)

        # 图例（白底半透明）
        self.legend = self.plot.addLegend(offset=(10, 10),
                                           labelTextColor=(31, 41, 55))
        self.legend.setPen(QPen(QColor(220, 220, 225)))
        self.legend.setBrush(QBrush(QColor(255, 255, 255, 220)))

        self.flow_curve = self.plot.plot(
            pen=pg.mkPen(color=(37, 99, 235), width=2),   # 主色蓝
            name='流量')
        self.inside_curve = self.plot.plot(
            pen=pg.mkPen(color=(217, 119, 6), width=2),   # 琥珀橙
            name='区域内数量')

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
        t_max = self._times[-1]
        self.flow_curve.setData(list(self._times), list(self._flow))
        self.inside_curve.setData(list(self._times), list(self._inside))
        start = max(0.0, t_max - MAX_HISTORY_SECONDS)
        self.plot.setXRange(start, t_max + self.sample_interval, padding=0.05)
        vals = list(self._flow) + list(self._inside)
        self.plot.setYRange(0, max(max(vals) * 1.2, 10), padding=0.05)

    def reset(self):
        self._times.clear()
        self._flow.clear()
        self._inside.clear()
        self._last_sample = -1.0
        self.flow_curve.setData([], [])
        self.inside_curve.setData([], [])
        self.plot.setXRange(0, 30, padding=0.05)
        self.plot.setYRange(0, 10, padding=0.1)
