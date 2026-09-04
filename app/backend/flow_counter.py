"""区域交通统计：基于 track_id 的区域进出状态转换，统计流量与停留时间。

由工作线程逐帧调用:
    counter = FlowCounter(polygon, fps=12.0, total_frames=N)
    stats = counter.update(tracks, frame_idx)
    frame = counter.draw_overlay(frame, stats, tracks)
"""
from collections import deque
from datetime import datetime

import cv2
import numpy as np

# 类别调色板（BGR）：0=行人(红) 1=机动车(蓝) 2=非机动车(绿)，与 config.yaml classes 对应
CLASS_COLORS = [
    (0, 0, 255),
    (255, 0, 0),
    (0, 200, 0),
    (255, 0, 255),
    (0, 165, 255),
    (255, 255, 0),
    (0, 255, 255),
    (200, 0, 0),
]


def class_color(cls_id):
    """按类别 id 取颜色（循环复用）。"""
    return CLASS_COLORS[cls_id % len(CLASS_COLORS)]


class FlowCounter:
    """区域交通统计器。

    参数:
        polygon    : 区域多边形顶点 [(x, y)]；None 表示整帧统计（目标恒在区域内）
        fps        : 视频帧率，用于帧数换算秒数
        total_frames: 视频总帧数，仅用于展示总时长
        window_seconds : 流量统计窗口时长（秒），统计窗口内流入区域的目标数
        congestion_threshold : 拥堵阈值，区域内数量超过该值时区域变红
    """

    def __init__(self, polygon=None, fps=25.0, total_frames=0,
                 window_seconds=1.0, congestion_threshold=5):
        self.polygon = polygon
        self.fps = max(float(fps), 1e-6)
        self.window_frames = int(window_seconds * self.fps)
        self.window_seconds = float(window_seconds)
        self.total_frames = int(total_frames)
        self.congestion_threshold = int(congestion_threshold)

        self._contour = (
            np.array(polygon, dtype=np.int32).reshape(-1, 1, 2)
            if polygon is not None else None)

        self._prev_inside = {}    # track_id -> 上一帧是否在区域内
        self._enter_frame = {}    # track_id -> 进入区域时的帧号
        self._inflow_events = deque()  # 进入事件帧号（滑动窗口）
        self._dwell_times = []    # 已完成的停留时长（秒）
        # 所有进入过区域的目标：区域内实时更新；离开后保留并冻结停留时间
        self._track_status = {}   # tid -> {'inside', 'class_id', 'confidence', 'dwell'}
        self.inflow = 0
        self.outflow = 0

    def reset(self):
        """重置所有计数与状态（区域参数不变）。"""
        self._prev_inside.clear()
        self._enter_frame.clear()
        self._inflow_events.clear()
        self._dwell_times.clear()
        self._track_status.clear()
        self.inflow = 0
        self.outflow = 0

    def update(self, tracks, frame_idx):
        """处理一帧跟踪结果，返回统计快照。

        状态机（每个 track_id）: 区域外→区域内 记流入并开始计时；
        区域内→区域外 记流出并冻结停留时间。
        """
        cur_inside = 0
        cur_inside_ids = set()

        for t in tracks:
            tid = t.get('track_id', -1)
            if tid is None or tid < 0:
                continue
            inside = self._is_inside(t['bbox'])
            prev = self._prev_inside.get(tid)

            if inside and prev is not True:       # 流入
                self.inflow += 1
                self._inflow_events.append(frame_idx)
                self._enter_frame[tid] = frame_idx
            elif not inside and prev is True:     # 流出
                self.outflow += 1
                ef = self._enter_frame.pop(tid, None)
                if ef is not None:
                    dwell = (frame_idx - ef) / self.fps
                    self._dwell_times.append(dwell)
                    if tid in self._track_status:
                        self._track_status[tid]['inside'] = False
                        self._track_status[tid]['dwell'] = dwell

            self._prev_inside[tid] = inside
            if inside:
                cur_inside += 1
                cur_inside_ids.add(tid)
                ef = self._enter_frame.get(tid, frame_idx)
                self._track_status[tid] = {
                    'inside': True,
                    'class_id': t.get('class_id', 0),
                    'confidence': float(t.get('confidence', 0.0)),
                    'dwell': (frame_idx - ef) / self.fps,
                }

        # 滑动窗口：清理窗口外的进入事件
        cutoff = frame_idx - self.window_frames
        while self._inflow_events and self._inflow_events[0] < cutoff:
            self._inflow_events.popleft()

        cur_dwells = [(frame_idx - self._enter_frame[tid]) / self.fps
                      for tid in cur_inside_ids if tid in self._enter_frame]
        return {
            'frame_idx': frame_idx,
            'inflow': self.inflow,
            'outflow': self.outflow,
            'current_inside': cur_inside,
            'flow_rate': len(self._inflow_events),
            'avg_dwell': (sum(self._dwell_times) / len(self._dwell_times)
                          if self._dwell_times else 0.0),
            'cur_avg_dwell': (sum(cur_dwells) / len(cur_dwells)
                              if cur_dwells else 0.0),
            'current_time': frame_idx / self.fps,
            'total_time': self.total_frames / self.fps,
            'window_seconds': self.window_seconds,
            'system_time': datetime.now().strftime('%H:%M:%S'),
            'track_status': {tid: dict(info) for tid, info in self._track_status.items()},
        }

    def _is_inside(self, bbox):
        """判断 bbox 中心是否在区域内（整帧模式恒为 True）。"""
        if self._contour is None:
            return True
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        return cv2.pointPolygonTest(self._contour, (float(cx), float(cy)), False) >= 0

    def draw_overlay(self, image, stats, tracks, scale=1.0):
        """绘制目标框与状态标签、区域多边形（拥堵变红）与左上角 FPS。

        标签（框色打底 + 白字）: 区域内 "#ID 置信度 停留s"，区域外仅置信度。
        scale 用于帧已缩放而 polygon 仍为原图坐标的情形。
        """
        for t in tracks:
            tid = t.get('track_id', -1)
            if tid is None or tid < 0:
                continue
            x1, y1, x2, y2 = (int(v) for v in t['bbox'])
            color = class_color(t.get('class_id', 0))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)

            st = self._track_status.get(tid)
            conf = t.get('confidence', 0.0)
            label = (f"#{tid} {conf:.2f} {st['dwell']:.1f}s"
                     if st is not None and st['inside'] else f"{conf:.2f}")
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image, (x1, y1 - th - 6), (x1 + tw + 4, y1 - 2), color, -1)
            cv2.putText(image, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if self._contour is not None:
            contour = self._contour if scale == 1.0 else (
                self._contour.astype(np.float32) * scale).astype(np.int32)
            congested = stats['current_inside'] > self.congestion_threshold
            fill = (0, 0, 200) if congested else (0, 200, 0)
            line = (0, 0, 255) if congested else (0, 255, 0)
            overlay = image.copy()
            cv2.fillPoly(overlay, [contour], fill)
            cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)
            cv2.polylines(image, [contour], True, line, 2)

        fps_val = stats.get('fps', 0.0)
        label = f"FPS: {fps_val:.1f}"
        font, fs, tk = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        (tw, th), _ = cv2.getTextSize(label, font, fs, tk)
        cv2.rectangle(image, (10, 10), (10 + tw + 16, 10 + th + 14), (0, 0, 0), -1)
        cv2.putText(image, label, (18, 10 + th + 4), font, fs, (0, 255, 255), tk)
        return image
