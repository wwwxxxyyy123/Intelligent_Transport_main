"""LLM 输出面板：AI 路况分析（Markdown）与目标列表两个标签页。

目标列表展示所有进入过区域的目标（ID/类别/当前位置/停留时间/置信度），
仅视频模式可用，图像模式下禁用。
"""
import time

from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QHeaderView, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from app.backend.llm_client import LLMClient
from app.config import Config
from app.frontend.theme import BTN_QSS


class LLMWorker(QThread):
    """后台 LLM 调用线程。"""

    analysis_done = pyqtSignal(bool, str, str)

    def __init__(self, traffic_stats, parent=None):
        super().__init__(parent)
        self.traffic_stats = traffic_stats

    def run(self):
        ok, text, err = LLMClient().analyze(self.traffic_stats)
        self.analysis_done.emit(ok, text, err)


class LLMPanel(QWidget):
    """LLM 路况分析输出面板。"""

    request_analysis = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.config = Config()
        self._llm_worker = None
        self._stats_history = []
        self._md_content = ""
        self._class_names_cn = self.config.get('classes', default={}) or {}

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        # 工具栏：标题 + 状态 + 分析按钮
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        title = QLabel("AI 路况分析")
        title.setObjectName("panelHead")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("secondaryLabel")
        toolbar.addWidget(self._status_label)
        self._analyze_btn = QPushButton("🤖 AI 分析")
        self._analyze_btn.setCursor(Qt.PointingHandCursor)
        self._analyze_btn.setMinimumHeight(34)
        self._analyze_btn.setStyleSheet(BTN_QSS)
        self._analyze_btn.clicked.connect(self._trigger)
        toolbar.addWidget(self._analyze_btn)
        root.addLayout(toolbar)

        self._tabs = QTabWidget()

        # Tab 1: AI 分析（Markdown 渲染）
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(8, 6, 8, 6)
        ai_layout.setSpacing(0)
        self._ai_output = QTextBrowser()
        self._ai_output.setOpenExternalLinks(True)
        self._ai_output.setPlaceholderText(
            '视频跟踪结束后将自动生成整体路况分析报告...\n\n'
            '也可点击上方 "🤖 AI 分析" 按钮手动触发。\n\n'
            '分析结果将以 Markdown 格式渲染，包含：\n'
            '• 当前交通状况评估    • 异常情况识别    • 改善建议')
        self._ai_output.document().setDefaultStyleSheet(_MARKDOWN_CSS)
        ai_layout.addWidget(self._ai_output)
        self._tabs.addTab(ai_tab, "🤖 AI 分析")

        # Tab 2: 目标列表
        targets_tab = QWidget()
        targets_layout = QVBoxLayout(targets_tab)
        targets_layout.setContentsMargins(8, 6, 8, 6)
        targets_layout.setSpacing(0)
        self._targets_table = QTableWidget(0, 5)
        self._targets_table.setHorizontalHeaderLabels(
            ["目标 ID", "类别名称", "当前位置", "区域内停留时间", "置信度"])
        self._targets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._targets_table.verticalHeader().setVisible(False)
        self._targets_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._targets_table.verticalHeader().setDefaultSectionSize(28)
        targets_layout.addWidget(self._targets_table)
        self._tab_targets_idx = self._tabs.addTab(targets_tab, "📋 目标列表")

        root.addWidget(self._tabs, stretch=1)

    # ---------- 数据更新 ----------
    def _cn_name(self, class_id):
        return self._class_names_cn.get(class_id, str(class_id))

    def set_targets_enabled(self, enabled):
        """启用/禁用目标列表 Tab（视频模式启用，图像模式禁用）。"""
        self._tabs.setTabEnabled(self._tab_targets_idx, enabled)
        self._tabs.setTabText(
            self._tab_targets_idx,
            "📋 目标列表" if enabled else "📋 目标列表（图像模式不可用）")

    def update_stats(self, stats):
        """缓存统计快照（供 LLM 分析），并按目标状态刷新列表。"""
        if not stats:
            return
        self._stats_history.append(stats)
        max_frames = self.config.get('llm', 'max_frames_for_analysis', default=300)
        if len(self._stats_history) > max_frames:
            self._stats_history = self._stats_history[-max_frames:]

        status = stats.get('track_status')
        if status is not None:
            self._rebuild_targets(status)

    def _rebuild_targets(self, status_map):
        """按 track_status 重建目标列表（离开区域的目标保留并置灰）。"""
        self._targets_table.clearContents()
        self._targets_table.setRowCount(0)
        self._targets_table.clearSpans()

        if not status_map:
            self._empty_hint("暂无目标进入区域")
            return

        for tid in sorted(status_map):
            info = status_map[tid]
            row = self._targets_table.rowCount()
            self._targets_table.insertRow(row)
            values = [
                str(tid),
                self._cn_name(info.get('class_id', 0)),
                "区域内" if info.get('inside') else "离开区域",
                f"{info.get('dwell', 0.0):.1f} 秒",
                f"{info.get('confidence', 0.0):.3f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if not info.get('inside'):
                    item.setForeground(Qt.gray)
                self._targets_table.setItem(row, col, item)

    def _empty_hint(self, text):
        self._targets_table.setRowCount(1)
        self._targets_table.setSpan(0, 0, 1, 5)
        hint = QTableWidgetItem(text)
        hint.setTextAlignment(Qt.AlignCenter)
        hint.setForeground(Qt.gray)
        self._targets_table.setItem(0, 0, hint)

    def reset(self):
        self._stats_history.clear()
        self._md_content = ""
        self._ai_output.clear()
        self._targets_table.clearContents()
        self._targets_table.setRowCount(0)
        self._status_label.setText("就绪")
        self._analyze_btn.setEnabled(True)

    # ---------- LLM 触发 ----------
    def analyze_full_session(self):
        """视频结束后自动触发整体分析。"""
        self._status_label.setText("视频结束，正在生成整体分析...")
        self._trigger()

    def _trigger(self):
        if self._llm_worker is not None and self._llm_worker.isRunning():
            return
        if not self._stats_history:
            self._status_label.setText("暂无足够数据进行分析")
            return
        self._status_label.setText("AI 分析中...")
        self._analyze_btn.setEnabled(False)
        self._llm_worker = LLMWorker(list(self._stats_history))
        self._llm_worker.analysis_done.connect(self._on_done)
        self._llm_worker.start()

    @pyqtSlot(bool, str, str)
    def _on_done(self, success, text, err):
        self._analyze_btn.setEnabled(True)
        if success:
            block = f"## 🕐 AI 路况分析 — {time.strftime('%H:%M:%S')}\n\n{text}\n\n---\n\n"
            self._status_label.setText("分析完成")
        else:
            block = (f"## ❌ 分析失败 — {time.strftime('%H:%M:%S')}\n\n"
                     f"**错误信息：** {err}\n\n"
                     f"请检查项目根目录 `.env` 中的 `AGNES_API_KEY` 与 `AGNES_BASE_URL`。\n\n---\n\n")
            self._status_label.setText("分析失败")
        self._md_content += block
        self._ai_output.setMarkdown(self._md_content)
        scrollbar = self._ai_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# Markdown 文档内 CSS（只作用于 QTextBrowser 文档，不涉及外层组件）
_MARKDOWN_CSS = """
    h1 { color:#1f2937; font-size:18px; border-bottom:2px solid #2563eb;
         padding-bottom:4px; margin-top:10px; }
    h2 { color:#1e40af; font-size:15px; margin-top:8px; }
    h3 { color:#374151; font-size:14px; margin-top:6px; }
    p  { line-height:1.7; margin:4px 0; }
    ul, ol { margin:4px 0; padding-left:20px; }
    li { margin:2px 0; line-height:1.6; }
    strong { color:#dc2626; }
    em { color:#7c3aed; }
    blockquote { border-left:3px solid #2563eb; margin:6px 0;
                 padding:4px 10px; background:#f1f5f9; color:#475569; }
    code { background:#f3f4f6; padding:2px 4px; border-radius:3px;
           font-family:Consolas,monospace; }
    hr { border:none; border-top:1px solid #e5e7eb; margin:10px 0; }
    table { border-collapse:collapse; margin:6px 0; }
    th, td { border:1px solid #e5e7eb; padding:4px 8px; }
    th { background:#2563eb; color:#ffffff; }
    tr:nth-child(even) td { background:#f9fafb; }
"""
