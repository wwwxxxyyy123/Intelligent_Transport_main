"""视频跟踪工作线程：后台消费 VideoTracker 生成器，避免阻塞 UI。

线程在 run() 中逐帧迭代后端 track_video() 生成器，并调用 FlowCounter
统计流量/停留/密度/时间、绘制区域与统计 overlay，每帧通过信号把结果推送到主线程。
emit 前将帧缩放到 display_width，大幅降低 QImage 构造与跨线程信号开销。
stop() 设置标志位，在下一次 yield 后安全中断（后端 finally 自动释放资源）。
"""
import time

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from app.backend.flow_counter import FlowCounter
from app.backend.tracker import VideoTracker
from app.config import Config


class VideoWorker(QThread):
    """后台视频跟踪 + 区域交通统计线程。"""

    # 每帧画面：(frame_idx, 标注图ndarray, 该帧跟踪列表)
    frame_ready = pyqtSignal(int, object, list)
    # 每帧统计：完整 stats dict（含流量/密度/停留/时间等）
    flow_stats = pyqtSignal(dict)
    # 状态文本（如"正在加载模型..."）
    status_msg = pyqtSignal(str)
    # 模型加载完成：传回类别 names dict，供主线程同步图例
    model_loaded = pyqtSignal(dict)
    # 正常结束 message
    tracking_finished = pyqtSignal(str)
    # 异常 message
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path, polygon=None, save_path=None,
                 congestion_threshold=5, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.polygon = polygon   # list[(x,y)] 或 None(整帧)
        self.save_path = save_path
        # 拥堵阈值（区域内数量 > 阈值时区域变红）；可被主线程运行中动态修改
        self.congestion_threshold = int(congestion_threshold)
        self._stop_flag = False
        # 显示缩放宽度（降低 QImage/信号开销）；0 表示不缩放
        self.config = Config()
        self.display_width = self.config.get('display', 'width', default=1280)

    def run(self):
        """线程入口：读取视频元数据 -> 加载模型 -> 逐帧跟踪+统计+绘制 -> 发射信号。"""
        try:
            # 1) 先用 cv2 读取视频元数据（fps/尺寸/总帧），供 FlowCounter 换算时间与面积
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开视频: {self.video_path}")
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()

            # 2) 加载模型（工作线程内，避免阻塞 UI）与统计器
            self.status_msg.emit("正在加载模型...")
            tracker = VideoTracker()
            # 通知主线程同步图例（names: {id: name}）
            self.model_loaded.emit(dict(tracker.names))
            # 从配置读取流量窗口时长
            window_seconds = self.config.get('traffic', 'flow_window_seconds', default=1.0)
            # polygon=None 时视为整帧；传入类名用于绘制图例
            counter = FlowCounter(self.polygon, fps=fps,
                                  frame_shape=(h, w, 3), total_frames=total,
                                  class_names=tracker.names,
                                  window_seconds=window_seconds,
                                  congestion_threshold=self.congestion_threshold)
            self.status_msg.emit("跟踪进行中...")

            # 3) 逐帧跟踪 + 统计 + 绘制
            # 关键优化：先缩放原图到显示尺寸，再在小图上绘制 overlay。
            # 绘制开销与帧面积成正比，4K(4096x2160)→1280x675 后绘制提速 ~10x。
            # tracks.bbox 同步缩放供小图绘制；draw_overlay 的 scale 参数负责
            # 缩放 _track_dwell(原图坐标) 和 polygon，使它们与小图对齐。
            orig_w = w
            scale = (self.display_width / orig_w) if (self.display_width and orig_w > self.display_width) else 1.0
            disp_w = int(orig_w * scale)
            disp_h = int(h * scale)
            # 处理帧率测量：指数滑动平均，用于画面 FPS 显示
            last_t = time.perf_counter()
            smooth_fps = 0.0
            for fr in tracker.track_video(self.video_path, save_path=self.save_path):
                if self._stop_flag:
                    break
                now = time.perf_counter()
                dt = now - last_t
                last_t = now
                if dt > 0:
                    inst_fps = 1.0 / dt
                    # EMA 平滑：前几帧快速收敛，之后稳定显示
                    smooth_fps = inst_fps if smooth_fps == 0.0 else (
                        0.9 * smooth_fps + 0.1 * inst_fps)
                stats = counter.update(fr.tracks, fr.frame_idx)
                # 同步拥堵阈值（主线程运行中可动态修改）
                counter.congestion_threshold = self.congestion_threshold
                # 注入处理帧率，供 draw_overlay 左上角显示
                stats['fps'] = smooth_fps
                # 先缩放原图到显示尺寸
                if scale != 1.0:
                    disp_frame = cv2.resize(fr.frame, (disp_w, disp_h),
                                            interpolation=cv2.INTER_AREA)
                    # bbox 坐标同步缩放，供 draw_overlay 在小图上绘制细框
                    scaled_tracks = []
                    for t in fr.tracks:
                        nt = dict(t)
                        x1, y1, x2, y2 = nt['bbox']
                        nt['bbox'] = [x1 * scale, y1 * scale, x2 * scale, y2 * scale]
                        scaled_tracks.append(nt)
                else:
                    disp_frame = fr.frame
                    scaled_tracks = fr.tracks
                # 在小图上绘制（开销大幅降低）；scale 用于缩放 _track_dwell/polygon
                frame = counter.draw_overlay(disp_frame, stats, scaled_tracks, scale=scale)
                self.frame_ready.emit(fr.frame_idx, frame, fr.tracks)
                self.flow_stats.emit(stats)
            self.tracking_finished.emit("已停止" if self._stop_flag else "跟踪完成")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        """请求停止（在下一帧 yield 后生效，保证后端清理资源）。"""
        self._stop_flag = True
