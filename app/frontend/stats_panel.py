"""右侧统计信息显示面板（objectName 化，无局部颜色 QSS）。

展示内容：时间信息 / 流量统计 / 流入流出 / 区域内数量。
所有文字视觉由全局 QSS 的 objectName（panelHead/cardTitle/largeNumber/secondaryLabel）
及 card 容器样式决定。
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
    QVBoxLayout, QWidget,
)


class StatsPanel(QWidget):
    """交通统计信息卡片面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._time_labels = {}
        self._flow_labels = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        title = QLabel("交通统计信息")
        title.setObjectName("panelHead")
        layout.addWidget(title)

        time_card, time_grid = self._create_card("时间信息")
        self._add_row(time_grid, self._time_labels, "系统时间", "sys_time", 0)
        self._add_row(time_grid, self._time_labels, "视频时间", "video_time", 1)
        layout.addWidget(time_card)

        flow_card, flow_grid = self._create_card("流量统计")
        self._add_row(flow_grid, self._flow_labels, "当前流量", "flow_rate", 0)
        self._add_row(flow_grid, self._flow_labels, "区域内数量", "inside", 1)
        self._add_row(flow_grid, self._flow_labels, "流入累计", "inflow", 2)
        self._add_row(flow_grid, self._flow_labels, "流出累计", "outflow", 3)
        layout.addWidget(flow_card)

        layout.addStretch()

    def _create_card(self, title):
        wrap = QWidget()
        wrap.setStyleSheet("background-color: transparent;")
        box = QVBoxLayout(wrap)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        t = QLabel(title)
        t.setObjectName("cardTitle")
        box.addWidget(t)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        box.addLayout(grid)
        return wrap, grid

    def _add_row(self, grid, label_dict, label_text, key, row):
        lbl = QLabel(label_text)
        lbl.setObjectName("secondaryLabel")

        val = QLabel("--")
        val.setObjectName("largeNumber")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val.setMinimumWidth(90)

        grid.addWidget(lbl, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(val, row, 1, Qt.AlignRight | Qt.AlignVCenter)
        label_dict[key] = val

    def update_stats(self, stats):
        """根据 FlowCounter.update() 返回的统计字典刷新所有卡片。"""
        self._time_labels['sys_time'].setText(stats.get('system_time', '--'))
        cur_t = stats.get('current_time', 0)
        tot_t = stats.get('total_time', 0)
        self._time_labels['video_time'].setText(
            f"{int(cur_t // 60):02d}:{int(cur_t % 60):02d} / "
            f"{int(tot_t // 60):02d}:{int(tot_t % 60):02d}")

        self._flow_labels['flow_rate'].setText(str(stats.get('flow_rate', 0)))
        self._flow_labels['inside'].setText(str(stats.get('current_inside', 0)))
        self._flow_labels['inflow'].setText(str(stats.get('inflow', 0)))
        self._flow_labels['outflow'].setText(str(stats.get('outflow', 0)))

    def reset(self):
        default = {
            'system_time': '--', 'current_time': 0, 'total_time': 0,
            'flow_rate': 0, 'current_inside': 0, 'inflow': 0, 'outflow': 0,
        }
        self.update_stats(default)
