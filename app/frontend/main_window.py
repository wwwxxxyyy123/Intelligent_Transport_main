"""主窗口（现代卡片区布局）：顶栏菜单 / 左(功能) / 中(视频+AI) / 右(图表+统计)。

新增顶层 QMenuBar：文件(F) / 视图(V) / 分析(A) / 帮助(H) 四菜单，等价于左侧按钮的快捷操作。

三栏 Splitter 比例：左 240 | 中 900 | 右 560（总 1700，适配 1080p）。
主窗口不再写任何局部 QSS，所有颜色/圆角/字体由 main.py 全局 QSS + objectName 接管。
"""
import cv2
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QFileDialog, QMainWindow, QMessageBox,
    QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from app.backend.detector import Detector
from app.config import Config
from app.frontend.button_panel import ButtonPanel
from app.frontend.chart_panel import ChartPanel
from app.frontend.image_viewer import ImageViewer
from app.frontend.llm_panel import LLMPanel
from app.frontend.stats_panel import StatsPanel
from app.frontend.video_worker import VideoWorker


class MainWindow(QMainWindow):
    """应用主窗口（顶部菜单 + 三栏卡片布局）。"""

    def __init__(self, detector=None):
        super().__init__()
        self.config = Config()

        app_name = self.config.get('system', 'app_name', default='智能交通检测系统')
        win_size = self.config.get('system', 'window_size', default=[1700, 960])
        self.setWindowTitle(app_name)
        self.resize(*win_size)
        self.setMinimumSize(1280, 780)

        self.detector = detector
        self.current_image_path = None
        self.current_image = None
        self.video_worker = None
        self._mode = "idle"
        self._pending_video_path = None

        self._setup_menubar()
        self._setup_ui()
        self._connect_signals()
        self._set_mode("idle")

        if self.detector is not None:
            self._sync_legend(self.detector.names)

    # ========== 菜单 ==========
    def _setup_menubar(self):
        mb = self.menuBar()

        # ---- 文件菜单 ----
        fm = mb.addMenu("文件(&F)")
        a_load = QAction("加载图像…", self)
        a_load.setShortcut(QKeySequence("Ctrl+O"))
        a_load.triggered.connect(self.on_load_image)
        fm.addAction(a_load)

        a_video = QAction("视频跟踪…", self)
        a_video.setShortcut(QKeySequence("Ctrl+Shift+V"))
        a_video.triggered.connect(self.on_video_track)
        fm.addAction(a_video)

        fm.addSeparator()

        a_clear = QAction("清空显示", self)
        a_clear.setShortcut(QKeySequence("Ctrl+D"))
        a_clear.triggered.connect(self.on_clear)
        fm.addAction(a_clear)

        fm.addSeparator()

        a_exit = QAction("退出", self)
        a_exit.setShortcut(QKeySequence.Quit)
        a_exit.triggered.connect(self.close)
        fm.addAction(a_exit)

        # ---- 视图菜单 ----
        vm = mb.addMenu("视图(&V)")
        self.act_finish = QAction("完成区域绘制", self)
        self.act_finish.setShortcut(QKeySequence("Enter"))
        self.act_finish.triggered.connect(self.on_finish_region)
        vm.addAction(self.act_finish)

        self.act_stop = QAction("停止 / 取消", self)
        self.act_stop.setShortcut(QKeySequence("Esc"))
        self.act_stop.triggered.connect(self.on_video_stop)
        vm.addAction(self.act_stop)

        # ---- 分析菜单 ----
        am = mb.addMenu("分析(&A)")
        a_infer = QAction("开始推理", self)
        a_infer.setShortcut(QKeySequence("Ctrl+R"))
        a_infer.triggered.connect(self.on_infer)
        am.addAction(a_infer)

        am.addSeparator()

        a_ai = QAction("🤖 AI 路况分析（手动）", self)
        a_ai.setShortcut(QKeySequence("Ctrl+G"))
        a_ai.triggered.connect(self._manual_ai)
        am.addAction(a_ai)

        # ---- 帮助菜单 ----
        hm = mb.addMenu("帮助(&H)")
        a_about = QAction("关于系统", self)
        a_about.triggered.connect(self._about)
        hm.addAction(a_about)

        a_help = QAction("操作说明", self)
        a_help.setShortcut(QKeySequence("F1"))
        a_help.triggered.connect(self._help)
        hm.addAction(a_help)

        # 菜单状态同步
        self._menu_actions = {
            'load': a_load, 'infer': a_infer, 'clear': a_clear,
            'video': a_video, 'finish': self.act_finish, 'stop': self.act_stop,
        }

    # ========== UI 组装 ==========
    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: transparent;")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # 三栏 Splitter（卡片之间的间距由 Splitter + 外边距保证；不再需要固定尺寸）
        self.button_panel = ButtonPanel()
        self.image_viewer = ImageViewer()
        self.llm_panel = LLMPanel()
        self.chart_panel = ChartPanel()
        self.stats_panel = StatsPanel()

        # 中栏：图像 + LLM 输出
        mid_splitter = QSplitter(Qt.Vertical)
        mid_splitter.addWidget(self.image_viewer)
        mid_splitter.addWidget(self.llm_panel)
        mid_splitter.setStretchFactor(0, 6)
        mid_splitter.setStretchFactor(1, 4)
        mid_splitter.setSizes([560, 360])
        mid_splitter.setHandleWidth(4)

        # 右栏：图表 + 统计
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.chart_panel)
        right_splitter.addWidget(self.stats_panel)
        right_splitter.setStretchFactor(0, 5)
        right_splitter.setStretchFactor(1, 4)
        right_splitter.setSizes([500, 380])
        right_splitter.setHandleWidth(4)

        # 主水平 Splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.button_panel)
        main_splitter.addWidget(mid_splitter)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)   # 左栏：固定宽度（Minimum 策略）
        main_splitter.setStretchFactor(1, 1)   # 中栏：占主空间
        main_splitter.setStretchFactor(2, 1)   # 右栏：占空间
        main_splitter.setSizes([240, 900, 560])
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(4)

        outer.addWidget(main_splitter)

    # ========== 信号连接 ==========
    def _connect_signals(self):
        self.button_panel.load_clicked.connect(self.on_load_image)
        self.button_panel.infer_clicked.connect(self.on_infer)
        self.button_panel.clear_clicked.connect(self.on_clear)
        self.button_panel.video_clicked.connect(self.on_video_track)
        self.button_panel.finish_region_clicked.connect(self.on_finish_region)
        self.button_panel.stop_clicked.connect(self.on_video_stop)
        self.button_panel.congestion_threshold_changed.connect(
            self.on_congestion_threshold_changed)

    # ========== 模式切换（左侧按钮 + 顶层菜单联动） ==========
    def _set_mode(self, mode):
        self._mode = mode
        self.button_panel.set_state(mode)
        is_idle = (mode == "idle")
        is_drawing = (mode == "drawing")
        is_tracking = (mode == "tracking")
        for k in ('load', 'infer', 'clear', 'video'):
            self._menu_actions[k].setEnabled(is_idle)
        self._menu_actions['finish'].setEnabled(is_drawing)
        self._menu_actions['stop'].setEnabled(is_drawing or is_tracking)

    # ========== 单图推理 ==========
    def on_load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图像", "", "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not path:
            return
        self.current_image_path = path
        self.current_image = cv2.imread(path)
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "无法读取该图像，请检查文件")
            return
        self.image_viewer.show_image(self.current_image)
        self.llm_panel.update_detections([])
        self.statusBar().showMessage(f"已加载图像: {path}")

    def on_infer(self):
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "请先加载图像")
            return
        if self.detector is None:
            QMessageBox.warning(self, "提示", "模型未加载，请重启程序")
            return
        try:
            _, detections = self.detector.predict(self.current_image_path)
            annotated = Detector.draw_detections(self.current_image.copy(), detections)
            self.image_viewer.show_image(annotated)
            self.llm_panel.update_detections(detections)
            self.statusBar().showMessage(f"推理完成，共检测到 {len(detections)} 个目标")
        except Exception as e:
            QMessageBox.critical(self, "推理失败", str(e))

    def _sync_legend(self, names):
        from app.backend.flow_counter import class_color
        config_classes = self.config.get('classes', default={}) or {}
        items = []
        for k in sorted(names):
            cid = int(k)
            cn = config_classes.get(cid, names[k])
            items.append((cn, class_color(cid)))
        self.button_panel.update_legend(items)

    def on_clear(self):
        self.current_image = None
        self.current_image_path = None
        self.image_viewer.clear()
        self.llm_panel.reset()
        self.chart_panel.reset()
        self.stats_panel.reset()
        self.statusBar().showMessage("已清空")

    # ========== 视频跟踪 ==========
    def on_video_track(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "", "Videos (*.mp4 *.avi *.mov *.mkv *.wmv)")
        if not path:
            return
        cap = cv2.VideoCapture(path)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            QMessageBox.warning(self, "提示", "无法读取视频首帧")
            return
        self._pending_video_path = path
        self._set_mode("drawing")
        self.image_viewer.enter_drawing_mode(frame)
        self.llm_panel.update_detections([])
        self.statusBar().showMessage(
            "左键添加区域顶点(≥3)，右键清空；点击[完成区域]开始跟踪；不选区域则整帧统计")

    def on_finish_region(self):
        if not self._pending_video_path:
            return
        points = self.image_viewer.get_points()
        polygon = points if len(points) >= 3 else None
        self.image_viewer.exit_drawing_mode()
        self._set_mode("tracking")

        self.chart_panel.reset()
        self.stats_panel.reset()
        self.llm_panel.reset()

        self.video_worker = VideoWorker(
            self._pending_video_path, polygon=polygon,
            congestion_threshold=self.button_panel.get_congestion_threshold())
        self.video_worker.frame_ready.connect(self.on_frame_ready)
        self.video_worker.flow_stats.connect(self.on_flow_stats)
        self.video_worker.status_msg.connect(self.statusBar().showMessage)
        self.video_worker.model_loaded.connect(self._sync_legend)
        self.video_worker.tracking_finished.connect(self.on_tracking_finished)
        self.video_worker.error_occurred.connect(self.on_worker_error)
        self.video_worker.start()

    def on_video_stop(self):
        if (self._mode == "tracking"
                and self.video_worker is not None
                and self.video_worker.isRunning()):
            self.video_worker.stop()
            self.statusBar().showMessage("正在停止...")
        elif self._mode == "drawing":
            self.image_viewer.exit_drawing_mode()
            self.image_viewer.clear()
            self._pending_video_path = None
            self._set_mode("idle")
            self.statusBar().showMessage("已取消区域选择")

    @pyqtSlot(int)
    def on_congestion_threshold_changed(self, value):
        if self.video_worker is not None:
            self.video_worker.congestion_threshold = int(value)
            self.statusBar().showMessage(f"拥堵阈值已更新为 {value}", 3000)

    @pyqtSlot(int, object, list)
    def on_frame_ready(self, frame_idx, annotated, tracks):
        self.image_viewer.show_image(annotated)
        self.llm_panel.update_detections(tracks)

    @pyqtSlot(dict)
    def on_flow_stats(self, stats):
        t = stats['current_time']
        self.statusBar().showMessage(
            f"系统 {stats['system_time']} | "
            f"视频 {int(t // 60):02d}:{int(t % 60):02d} | "
            f"流量 {stats['flow_rate']} | "
            f"流入 {stats['inflow']} 流出 {stats['outflow']} 区域内 {stats['current_inside']} | "
            f"平均停留 {stats['avg_dwell']:.1f}s")
        self.stats_panel.update_stats(stats)
        self.chart_panel.update_stats(stats)
        self.llm_panel.update_stats(stats)

    @pyqtSlot(str)
    def on_tracking_finished(self, msg):
        self._pending_video_path = None
        self.video_worker = None
        self._set_mode("idle")
        self.statusBar().showMessage(f"跟踪完成: {msg}，正在生成 AI 分析...", 5000)
        self.llm_panel.analyze_full_session()

    @pyqtSlot(str)
    def on_worker_error(self, msg):
        self._pending_video_path = None
        self.video_worker = None
        self._set_mode("idle")
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "视频跟踪失败", msg)

    # ========== 菜单辅助 ==========
    def _manual_ai(self):
        self.llm_panel._trigger() if hasattr(self.llm_panel, '_trigger') else None

    def _about(self):
        QMessageBox.about(
            self, "关于系统",
            "<h3>智能交通检测系统 v2.1</h3>"
            "<p>基于 YOLO 的多目标检测与路况分析原型软件。</p>"
            "<ul>"
            "<li>单图目标检测推理</li>"
            "<li>视频多目标区域跟踪与统计（流量/停留/拥堵判定）</li>"
            "<li>大语言模型（Agnes AI）智能路况分析</li>"
            "<li>实时曲线图与统计面板</li>"
            "</ul>")

    def _help(self):
        QMessageBox.information(
            self, "操作说明",
            """<h4>基础操作</h4>
<ul>
<li><b>加载图像（Ctrl+O）</b>：选择本地图片并显示。</li>
<li><b>开始推理（Ctrl+R）</b>：对已加载图片执行 YOLO 检测。</li>
<li><b>清空显示（Ctrl+D）</b>：清空图像/目标/图表。</li>
</ul>
<h4>视频区域跟踪</h4>
<ul>
<li><b>视频跟踪（Ctrl+Shift+V）</b>：选择视频文件并进入区域绘制模式。</li>
<li>左键点击添加区域顶点（≥3 个），右键清空顶点。</li>
<li><b>完成区域（Enter）</b>：开始后台跟踪统计。未选区域则整帧统计。</li>
<li><b>停止（Esc）</b>：跟踪过程中随时停止。</li>
</ul>
<h4>其他</h4>
<ul>
<li><b>拥堵阈值</b>：区域内目标数量超过阈值时区域变红提示拥堵。</li>
<li><b>AI 路况分析（Ctrl+G）</b>：视频结束会自动生成，也可手动触发。</li>
</ul>
""")
