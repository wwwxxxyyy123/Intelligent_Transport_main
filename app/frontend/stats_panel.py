"""右侧统计信息面板：KPI 卡片 + 时间信息 + 视频进度。

视觉：颜色/边框由全局 QSS 的 objectName（card/tile/statValue*）驱动，
本文件只负责结构——四个 KPI 数字块、时间信息行、视频进度条。
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QSizePolicy, QVBoxLayout, QWidget,
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("交通统计信息")
        title.setObjectName("panelHead")
        layout.addWidget(title)

        # ---- 四个 KPI 数字块（2x2） ----
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)
        self._add_kpi(kpi_grid, self._flow_labels, "当前流量", "flow_rate",
                      0, 0, "statValue", "辆 / 窗口")
        self._add_kpi(kpi_grid, self._flow_labels, "区域内数量", "inside",
                      0, 1, "statValueWarn", "目标数")
        self._add_kpi(kpi_grid, self._flow_labels, "流入累计", "inflow",
                      1, 0, "statValueOk", "累计")
        self._add_kpi(kpi_grid, self._flow_labels, "流出累计", "outflow",
                      1, 1, "statValueInfo", "累计")
        layout.addLayout(kpi_grid)

        # ---- 时间信息 + 视频进度 ----
        time_tile = QFrame()
        time_tile.setObjectName("tile")
        time_box = QVBoxLayout(time_tile)
        time_box.setContentsMargins(12, 10, 12, 12)
        time_box.setSpacing(8)

        time_title = QLabel("时间信息")
        time_title.setObjectName("cardTitle")
        time_box.addWidget(time_title)

        time_box.addLayout(self._time_row("系统时间", "sys_time"))
        time_box.addLayout(self._time_row("视频时间", "video_time"))

        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        progress_label = QLabel("视频进度")
        progress_label.setObjectName("mutedLabel")
        progress_label.setFixedWidth(64)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        # 百分比放在进度条外侧，浅色主题下始终可读
        self._progress_value = QLabel("0%")
        self._progress_value.setObjectName("monoValue")
        self._progress_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._progress_value.setFixedWidth(40)
        progress_row.addWidget(progress_label)
        progress_row.addWidget(self._progress, stretch=1)
        progress_row.addWidget(self._progress_value)
        time_box.addLayout(progress_row)

        layout.addWidget(time_tile)
        layout.addStretch()

    # ---------- UI 片段 ----------
    def _add_kpi(self, grid, label_dict, label_text, key, row, col, value_style, unit):
        tile = QFrame()
        tile.setObjectName("tile")
        box = QVBoxLayout(tile)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(4)
        name = QLabel(label_text)
        name.setObjectName("secondaryLabel")
        top.addWidget(name)
        top.addStretch()
        unit_label = QLabel(unit)
        unit_label.setObjectName("emptyHint")
        top.addWidget(unit_label)
        box.addLayout(top)

        val = QLabel("0")
        val.setObjectName(value_style)
        val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        box.addWidget(val)

        grid.addWidget(tile, row, col)
        label_dict[key] = val

    def _time_row(self, label_text, key):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setObjectName("secondaryLabel")
        val = QLabel("--")
        val.setObjectName("monoValue")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        self._time_labels[key] = val
        return row

    # ---------- 数据刷新 ----------
    def update_stats(self, stats):
        """根据 FlowCounter.update() 返回的统计字典刷新所有卡片。"""
        self._time_labels['sys_time'].setText(str(stats.get('system_time', '--')))
        cur_t = stats.get('current_time', 0)
        tot_t = stats.get('total_time', 0)
        self._time_labels['video_time'].setText(
            f"{int(cur_t // 60):02d}:{int(cur_t % 60):02d} / "
            f"{int(tot_t // 60):02d}:{int(tot_t % 60):02d}")

        if tot_t and tot_t > 0:
            pct = max(0, min(100, int(cur_t / tot_t * 100)))
        else:
            pct = 0
        self._progress.setValue(pct)
        self._progress_value.setText(f"{pct}%")

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
        self._progress.setValue(0)
        self._progress_value.setText("0%")
