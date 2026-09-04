"""视频跟踪工作线程：后台消费 VideoTracker 生成器，避免阻塞 UI。

逐帧调用 FlowCounter 统计并绘制 overlay，通过信号推送结果到主线程；
帧先缩放到显示尺寸再绘制，降低图像构造与跨线程信号开销。
"""
import time

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from app.backend.flow_counter import FlowCounter
from app.backend.tracker import VideoTracker
from app.config import Config


class VideoWorker(QThread):
    """后台视频跟踪 + 区域交通统计线程。"""

    frame_ready = pyqtSignal(int, object, list)   # (frame_idx, 标注帧, tracks)
    flow_stats = pyqtSignal(dict)                 # 每帧统计快照
    status_msg = pyqtSignal(str)
    model_loaded = pyqtSignal(dict)               # 类别 names，供图例同步
    tracking_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path, polygon=None, save_path=None,
                 congestion_threshold=5, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.polygon = polygon                     # [(x, y)] 或 None（整帧）
        self.save_path = save_path
        self.congestion_threshold = int(congestion_threshold)  # 可在运行中动态修改
        self._stop_flag = False
        self.config = Config()
        self.display_width = self.config.get('display', 'width', default=1280)

    def run(self):
        try:
            fps, w, h, total = self._read_meta()

            self.status_msg.emit("正在加载模型...")
            tracker = VideoTracker()
            self.model_loaded.emit(dict(tracker.names))

            counter = FlowCounter(
                self.polygon, fps=fps, total_frames=total,
                window_seconds=self.config.get('traffic', 'flow_window_seconds', default=1.0),
                congestion_threshold=self.congestion_threshold)
            self.status_msg.emit("跟踪进行中...")

            scale, disp_size = self._display_scale(w, h)
            smooth_fps = 0.0
            last_t = time.perf_counter()
            for fr in tracker.track_video(self.video_path, save_path=self.save_path):
                if self._stop_flag:
                    break
                smooth_fps, last_t = self._ema_fps(smooth_fps, last_t)

                stats = counter.update(fr.tracks, fr.frame_idx)
                counter.congestion_threshold = self.congestion_threshold
                stats['fps'] = smooth_fps

                disp_frame, disp_tracks = self._scale_frame(fr, scale, disp_size)
                frame = counter.draw_overlay(disp_frame, stats, disp_tracks, scale=scale)
                self.frame_ready.emit(fr.frame_idx, frame, fr.tracks)
                self.flow_stats.emit(stats)

            self.tracking_finished.emit("已停止" if self._stop_flag else "跟踪完成")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        """请求停止（下一帧生效，后端 finally 自动释放资源）。"""
        self._stop_flag = True

    def _read_meta(self):
        """读取视频元数据，返回 (fps, 宽, 高, 总帧数)。"""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频: {self.video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return fps, w, h, total

    def _display_scale(self, w, h):
        """超过显示宽度才缩放，返回 (scale, 缩放后尺寸)。"""
        if self.display_width and w > self.display_width:
            scale = self.display_width / w
            return scale, (int(w * scale), int(h * scale))
        return 1.0, (w, h)

    @staticmethod
    def _ema_fps(prev, last_t):
        """指数滑动平均计算处理帧率，返回 (smooth_fps, 新时间戳)。"""
        now = time.perf_counter()
        dt = now - last_t
        if dt > 0:
            inst = 1.0 / dt
            prev = inst if prev == 0.0 else 0.9 * prev + 0.1 * inst
        return prev, now

    def _scale_frame(self, fr, scale, disp_size):
        """按显示尺寸缩放帧与 bbox；无需缩放时原样返回。"""
        if scale == 1.0:
            return fr.frame, fr.tracks
        frame = cv2.resize(fr.frame, disp_size, interpolation=cv2.INTER_AREA)
        tracks = []
        for t in fr.tracks:
            nt = dict(t)
            x1, y1, x2, y2 = nt['bbox']
            nt['bbox'] = [x1 * scale, y1 * scale, x2 * scale, y2 * scale]
            tracks.append(nt)
        return frame, tracks
