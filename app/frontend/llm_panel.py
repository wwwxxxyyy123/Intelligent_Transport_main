"""LLM 输出面板（objectName 化，无局部颜色/边框 QSS）。

包含两个标签页：
- 🤖 AI 分析：Markdown 渲染的整体路况分析（视频结束自动生成 / 手动触发）
- 📋 目标列表：区域内目标的 ID / 类别 / 停留时间 / 置信度
"""
import time

from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QHeaderView, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from app.backend.llm_client import LLMClient
from app.config import Config


# ---- 后台 LLM 调用线程 ----
class LLMWorker(QThread):
    analysis_done = pyqtSignal(bool, str, str)

    def __init__(self, detections, traffic_stats, parent=None):
        super().__init__(parent)
        self.detections = detections
        self.traffic_stats = traffic_stats

    def run(self):
        client = LLMClient()
        ok, text, err = client.analyze(self.detections, self.traffic_stats)
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
        self._current_detections = []
        self._md_content = ""
        self._class_names_cn = self.config.get('classes', default={}) or {}

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        # 工具栏
        tb = QHBoxLayout()
        tb.setSpacing(10)
        title = QLabel("AI 路况分析")
        title.setObjectName("panelHead")
        tb.addWidget(title)
        tb.addStretch()
        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("secondaryLabel")
        tb.addWidget(self._status_label)
        self._analyze_btn = QPushButton("🤖 AI 分析")
        self._analyze_btn.setProperty("btnRole", "warn")
        self._analyze_btn.setCursor(Qt.PointingHandCursor)
        self._analyze_btn.setMinimumHeight(34)
        self._analyze_btn.clicked.connect(self._on_analyze_clicked)
        tb.addWidget(self._analyze_btn)
        root.addLayout(tb)

        # 标签页容器（透明内层，外层已由 card 负责圆角）
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(False)

        # Tab 1: AI 分析 Markdown 渲染
        self._ai_tab = QWidget()
        ai_l = QVBoxLayout(self._ai_tab)
        ai_l.setContentsMargins(8, 6, 8, 6)
        ai_l.setSpacing(0)
        self._ai_output = QTextBrowser()
        self._ai_output.setOpenExternalLinks(True)
        self._ai_output.setPlaceholderText(
            '视频跟踪结束后将自动生成整体路况分析报告...\n\n'
            '也可点击上方 "🤖 AI 分析" 按钮手动触发。\n\n'
            '分析结果将以 Markdown 格式渲染，包含：\n'
            '• 当前交通状况评估    • 异常情况识别    • 改善建议')
        # Markdown 文档 CSS（保持与主色板一致，不涉及外层组件样式）
        self._ai_output.document().setDefaultStyleSheet("""
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
        """)
        ai_l.addWidget(self._ai_output)
        self._tabs.addTab(self._ai_tab, "🤖 AI 分析")

        # Tab 2: 目标列表
        self._targets_tab = QWidget()
        tg_l = QVBoxLayout(self._targets_tab)
        tg_l.setContentsMargins(8, 6, 8, 6)
        tg_l.setSpacing(0)
        self._targets_table = QTableWidget(0, 4)
        self._targets_table.setHorizontalHeaderLabels(
            ["目标 ID", "类别名称", "区域内停留时间", "置信度"])
        self._targets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._targets_table.verticalHeader().setVisible(False)
        self._targets_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._targets_table.verticalHeader().setDefaultSectionSize(28)
        tg_l.addWidget(self._targets_table)
        self._tabs.addTab(self._targets_tab, "📋 目标列表")

        root.addWidget(self._tabs, stretch=1)

    # ---------- 数据更新 ----------
    def _cn_name(self, det):
        cid = det.get('class_id', 0)
        return self._class_names_cn.get(cid, det.get('class_name', '未知'))

    def update_detections(self, detections):
        self._current_detections = detections
        if not self._stats_history:
            self._rebuild(detections, dwell_map=None)

    def update_stats(self, stats):
        if not stats:
            return
        self._stats_history.append(stats)
        max_frames = self.config.get('llm', 'max_frames_for_analysis', default=300)
        if len(self._stats_history) > max_frames:
            self._stats_history = self._stats_history[-max_frames:]

        dwell = stats.get('track_dwells')
        if dwell is not None:
            self._rebuild(self._current_detections, dwell)

    def _rebuild(self, detections, dwell_map):
        self._targets_table.clearContents()
        self._targets_table.setRowCount(0)
        self._targets_table.clearSpans()

        if dwell_map is not None:
            inside = []
            for det in detections:
                tid = det.get('track_id', -1)
                if tid is not None and tid >= 0 and tid in dwell_map:
                    info = dwell_map[tid]
                    inside.append({
                        'id': tid, 'name': self._cn_name(det),
                        'dwell': info.get('dwell', 0.0),
                        'conf': det.get('confidence', 0),
                    })
            if not inside:
                self._empty_hint("区域内暂无目标")
                return
            rows = inside
        else:
            if not detections:
                self._empty_hint("暂无检测结果")
                return
            rows = []
            for i, d in enumerate(detections, start=1):
                tid = d.get('track_id', -1)
                rows.append({
                    'id': str(tid) if tid is not None and tid >= 0 else i,
                    'name': self._cn_name(d),
                    'dwell': None,
                    'conf': d.get('confidence', 0),
                })

        for r in rows:
            row = self._targets_table.rowCount()
            self._targets_table.insertRow(row)
            dwell_s = f"{r['dwell']:.1f} 秒" if r['dwell'] is not None else "--"
            vals = [str(r['id']), r['name'], dwell_s, f"{r['conf']:.3f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                self._targets_table.setItem(row, c, it)

    def _empty_hint(self, text):
        self._targets_table.setRowCount(1)
        self._targets_table.setSpan(0, 0, 1, 4)
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter)
        it.setForeground(Qt.gray)
        self._targets_table.setItem(0, 0, it)

    def reset(self):
        self._stats_history.clear()
        self._current_detections = []
        self._md_content = ""
        self._ai_output.clear()
        self._targets_table.clearContents()
        self._targets_table.setRowCount(0)
        self._status_label.setText("就绪")
        self._analyze_btn.setEnabled(True)

    # ---------- LLM 触发 ----------
    def _on_analyze_clicked(self):
        self._trigger()

    def analyze_full_session(self):
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
        self._llm_worker = LLMWorker(list(self._current_detections),
                                     list(self._stats_history))
        self._llm_worker.analysis_done.connect(self._on_done)
        self._llm_worker.start()

    @pyqtSlot(bool, str, str)
    def _on_done(self, success, text, err):
        self._analyze_btn.setEnabled(True)
        if success:
            ts = time.strftime('%H:%M:%S')
            block = f"## 🕐 AI 路况分析 — {ts}\n\n{text}\n\n---\n\n"
            self._md_content += block
            self._ai_output.setMarkdown(self._md_content)
            sb = self._ai_output.verticalScrollBar()
            sb.setValue(sb.maximum())
            self._status_label.setText("分析完成")
        else:
            self._status_label.setText(f"分析失败")
            m = (f"## ❌ 分析失败 — {time.strftime('%H:%M:%S')}\n\n"
                 f"**错误信息：** {err}\n\n"
                 f"请检查项目根目录 `.env` 中的 `AGNES_API_KEY` 与 `AGNES_BASE_URL`。\n\n---\n\n")
            self._md_content += m
            self._ai_output.setMarkdown(self._md_content)
