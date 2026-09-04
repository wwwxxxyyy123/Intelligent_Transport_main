"""主窗口：三栏卡片布局（左功能 / 中视频+AI / 右图表+统计）。"""
import cv2
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget,
)

from app.backend.detector import Detector
from app.backend.flow_counter import class_color
from app.config import Config
from app.frontend.button_panel import ButtonPanel
from app.frontend.chart_panel import ChartPanel
from app.frontend.image_viewer import ImageViewer
from app.frontend.llm_panel import LLMPanel
from app.frontend.stats_panel import StatsPanel
from app.frontend.video_worker import VideoWorker


class MainWindow(QMainWindow):
    """应用主窗口。"""

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

        self._setup_ui()
        self._connect_signals()
        self._set_mode("idle")

        if self.detector is not None:
            self._sync_legend(self.detector.names)

    # ---------- UI 组装 ----------
    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: transparent;")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        self.button_panel = ButtonPanel()
        self.image_viewer = ImageViewer()
        self.llm_panel = LLMPanel()
        self.chart_panel = ChartPanel()
        self.stats_panel = StatsPanel()

        mid = self._v_splitter(self.image_viewer, self.llm_panel, [560, 360], 6, 4)
        right = self._v_splitter(self.chart_panel, self.stats_panel, [500, 380], 5, 4)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.button_panel)
        main_splitter.addWidget(mid)
        main_splitter.addWidget(right)
        main_splitter.setStretchFactor(0, 0)   # 左栏固定宽度
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 1)
        main_splitter.setSizes([240, 900, 560])
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(4)
        outer.addWidget(main_splitter)

    @staticmethod
    def _v_splitter(top, bottom, sizes, stretch_top, stretch_bottom):
        """构建上下分割的 QSplitter。"""
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, stretch_top)
        splitter.setStretchFactor(1, stretch_bottom)
        splitter.setSizes(sizes)
        splitter.setHandleWidth(4)
        return splitter

    def _connect_signals(self):
        self.button_panel.load_clicked.connect(self.on_load_image)
        self.button_panel.infer_clicked.connect(self.on_infer)
        self.button_panel.clear_clicked.connect(self.on_clear)
        self.button_panel.video_clicked.connect(self.on_video_track)
        self.button_panel.finish_region_clicked.connect(self.on_finish_region)
        self.button_panel.stop_clicked.connect(self.on_video_stop)
        self.button_panel.congestion_threshold_changed.connect(
            self.on_congestion_threshold_changed)

    def _set_mode(self, mode):
        self._mode = mode
        self.button_panel.set_state(mode)

    # ---------- 图像模式 ----------
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
        self.llm_panel.set_targets_enabled(False)
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
            self.statusBar().showMessage(f"推理完成，共检测到 {len(detections)} 个目标")
        except Exception as e:
            QMessageBox.critical(self, "推理失败", str(e))

    def _sync_legend(self, names):
        config_classes = self.config.get('classes', default={}) or {}
        items = [(config_classes.get(int(k), names[k]), class_color(int(k)))
                 for k in sorted(names)]
        self.button_panel.update_legend(items)

    def on_clear(self):
        self.current_image = None
        self.current_image_path = None
        self.image_viewer.clear()
        self.llm_panel.reset()
        self.llm_panel.set_targets_enabled(True)
        self.chart_panel.reset()
        self.stats_panel.reset()
        self.statusBar().showMessage("已清空")

    # ---------- 视频模式 ----------
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
        self.llm_panel.set_targets_enabled(True)
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

    # ---------- 工作线程回调 ----------
    @pyqtSlot(int)
    def on_congestion_threshold_changed(self, value):
        if self.video_worker is not None:
            self.video_worker.congestion_threshold = int(value)
            self.statusBar().showMessage(f"拥堵阈值已更新为 {value}", 3000)

    @pyqtSlot(int, object, list)
    def on_frame_ready(self, frame_idx, annotated, tracks):
        self.image_viewer.show_image(annotated)

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
