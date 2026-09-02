"""区域交通统计后端：基于 track_id 在区域内外的状态转换，统计
流量、车辆停留时间、时间信息。

无 Qt 依赖，纯 cv2/numpy/datetime，由工作线程逐帧调用：
    counter = FlowCounter(polygon, fps=12.0, frame_shape=(h,w,3), total_frames=N)
    stats = counter.update(tracks, frame_idx)   # 每帧更新
    frame = counter.draw_overlay(frame, stats)  # 在帧上绘制区域、统计与每个目标停留时间

关键设计（满足需求）:
- 流量   = 窗口时长（由配置 flow_window_seconds 决定，默认 1s）内流入区域的数量，
           用"最近 window_frames 帧"滑动窗口统计进入事件数。
- 停留时间 = 每个 track_id 从进入区域到当前(或离开)所用的秒数（帧差 / fps）。
           每个目标单独标注，绘制在其 bbox 上方；stats 中亦返回 per-track 字典。
- 时间信息 = 当前视频时间(frame_idx/fps) + 当前系统时间(datetime.now)。
"""
from collections import deque
from datetime import datetime

import cv2
import numpy as np

# 类别颜色调色板（BGR）：对比鲜明，目标框本身颜色明显易辨
# 按类 id 顺序分配；超出范围的类循环复用
# 类别映射（config.yaml）: 0=行人 1=机动车 2=非机动车（绿色）
CLASS_COLORS = [
    (0, 0, 255),      # 0 行人: 红
    (255, 0, 0),      # 1 机动车: 蓝
    (0, 200, 0),      # 2 非机动车: 绿
    (255, 0, 255),    # 紫
    (0, 165, 255),    # 橙
    (255, 255, 0),    # 青
    (0, 255, 255),    # 黄
    (200, 0, 0),      # 暗蓝
]


def class_color(cls_id):
    """按类 id 取颜色（循环复用）。"""
    return CLASS_COLORS[cls_id % len(CLASS_COLORS)]


class FlowCounter:
    """区域交通统计器。

    参数:
        polygon      : 区域多边形顶点 list[(x,y)] / np.ndarray（图像坐标）；
                       为 None 时视为整帧范围，所有目标恒在区域内。
        fps          : 视频帧率，用于把帧数换算为秒。
        frame_shape  : 整帧模式用于兼容旧接口（保留参数，不再参与计算）。
        total_frames : 视频总帧数，用于显示总时长（仅展示用）。
        class_names  : 类别名称映射 {id: name}，用于绘制图例；未提供则用类 id 文本。
        window_seconds : 流量统计窗口时长（秒），默认 1.0，即统计最近 N 秒内进入区域的车辆数。
        congestion_threshold : 拥堵阈值，区域内数量大于该值时区域变红提示拥堵。
    """

    def __init__(self, polygon=None, fps=25.0, frame_shape=None, total_frames=0,
                 class_names=None, window_seconds=1.0, congestion_threshold=5):
        self.polygon = polygon
        self.fps = max(float(fps), 1e-6)                       # 防止除 0
        self.window_frames = int(window_seconds * self.fps)    # 窗口时长对应的帧数
        self.total_frames = int(total_frames)
        # 类别名称映射 {id: name}，用于绘制图例；未提供则用类 id 文本
        self.class_names = class_names or {}
        # 拥堵阈值（区域内数量 > 该值时区域变红）；支持运行中动态修改
        self.congestion_threshold = int(congestion_threshold)

        # cv2 多边形接口需要 (N,1,2) int32 轮廓
        self._contour = (
            np.array(polygon, dtype=np.int32).reshape(-1, 1, 2)
            if polygon is not None else None
        )

        # ---- 状态机：区域内外转换 ----
        self._prev_inside = {}   # track_id -> bool（上一帧是否在区域内）
        self.inflow = 0          # 累计流入
        self.outflow = 0         # 累计流出

        # ---- 流量滑动窗口：记录每次进入事件的帧号 ----
        self._inflow_events = deque()

        # ---- 停留时间追踪 ----
        self._enter_frame = {}    # track_id -> 进入区域时的帧号
        self._dwell_times = []    # 已完成停留时间（秒）
        # 目标状态追踪：所有"进入过区域"的目标（进入时加入列表，离开后保留并
        # 把当前位置置为"离开区域"，停留时间冻结），供目标列表动态更新
        self._track_status = {}   # tid -> {'inside': bool, 'class_id', 'confidence', 'dwell'}

    def reset(self):
        """重置所有计数与状态（区域/面积参数不变）。"""
        self._prev_inside.clear()
        self.inflow = 0
        self.outflow = 0
        self._inflow_events.clear()
        self._enter_frame.clear()
        self._dwell_times.clear()
        self._track_status.clear()

    def update(self, tracks, frame_idx):
        """处理一帧 tracks，更新累计指标并返回当前统计字典。

        状态机（每个 track_id）:
            非内(首次/False) -> 内  : 流入 +1，记录进入帧号
            内(True)         -> 外  : 流出 +1，结算停留时间
        """
        cur_inside = 0
        cur_inside_ids = set()

        for t in tracks:
            tid = t.get('track_id', -1)
            if tid is None or tid < 0:
                continue  # 跟踪器未分配 id 的目标跳过
            inside = self._is_inside(t['bbox'])
            prev = self._prev_inside.get(tid)   # None/True/False

            if inside and prev is not True:            # 非内→内：流入
                self.inflow += 1
                self._inflow_events.append(frame_idx)
                self._enter_frame[tid] = frame_idx
            elif (not inside) and prev is True:         # 内→外：流出
                self.outflow += 1
                ef = self._enter_frame.pop(tid, None)
                if ef is not None:
                    dwell = (frame_idx - ef) / self.fps
                    self._dwell_times.append(dwell)
                    # 离开区域：冻结最终停留时间，位置置为"离开区域"
                    if tid in self._track_status:
                        self._track_status[tid]['inside'] = False
                        self._track_status[tid]['dwell'] = dwell

            self._prev_inside[tid] = inside
            if inside:
                cur_inside += 1
                cur_inside_ids.add(tid)
                # 区域内目标：实时更新停留时间与最新类别/置信度（首次进入即加入列表）
                ef = self._enter_frame.get(tid, frame_idx)
                self._track_status[tid] = {
                    'inside': True,
                    'class_id': t.get('class_id', 0),
                    'confidence': float(t.get('confidence', 0.0)),
                    'dwell': (frame_idx - ef) / self.fps,
                }

        # 清理过期进入事件（滑动窗口只保留窗口时长内的事件）
        cutoff = frame_idx - self.window_frames
        while self._inflow_events and self._inflow_events[0] < cutoff:
            self._inflow_events.popleft()

        # 流量：单位时间内流入区域的数量 = 窗口时长内进入事件数
        flow_rate = len(self._inflow_events)

        # 已完成停留时间的平均值（秒）
        avg_dwell = (sum(self._dwell_times) / len(self._dwell_times)
                     if self._dwell_times else 0.0)

        # 当前仍在区域内目标的实时停留平均值（秒）
        cur_dwells = [(frame_idx - self._enter_frame[tid]) / self.fps
                      for tid in cur_inside_ids if tid in self._enter_frame]
        cur_avg_dwell = (sum(cur_dwells) / len(cur_dwells) if cur_dwells else 0.0)

        return {
            'frame_idx': frame_idx,
            'inflow': self.inflow,
            'outflow': self.outflow,
            'current_inside': cur_inside,    # 区域内当前车辆数
            'flow_rate': flow_rate,          # 窗口时长内流入数量
            'avg_dwell': avg_dwell,          # 平均停留秒数（已完成）
            'cur_avg_dwell': cur_avg_dwell,  # 当前在区域内目标平均停留秒数
            'current_time': frame_idx / self.fps,          # 当前视频时间(秒)
            'total_time': self.total_frames / self.fps,    # 总时长(秒)
            'system_time': datetime.now().strftime('%H:%M:%S'),  # 当前系统时间
            # 所有进入过区域的目标状态 {tid: {'inside', 'class_id', 'confidence', 'dwell'}}
            # 区域内目标实时更新；离开区域的目标保留（位置=离开区域，停留时间冻结）
            'track_status': {tid: dict(info) for tid, info in self._track_status.items()},
        }

    def _is_inside(self, bbox):
        """判断 bbox 中心是否落在区域内（整帧模式恒为 True）。"""
        if self._contour is None:
            return True
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        # measureDist=False: 返回 +1(内) / 0(边) / -1(外)
        return cv2.pointPolygonTest(self._contour, (float(cx), float(cy)), False) >= 0

    def draw_overlay(self, image, stats, tracks, scale=1.0):
        """在图像上绘制：每个目标按类别的细框 + 状态标签、区域多边形
        （拥堵时变红）、左上角 FPS 信息。

        目标标签规则（框色打底 + 白色文字，位于 bbox 上方）:
            目标在区域内  -> "#ID 置信度 停留时间"   如 "#3 0.87 5.2s"
            目标不在区域  -> 仅置信度               如 "0.87"

        参数:
            image : BGR 帧（原地绘制）
            stats : update() 返回的统计字典（可含 'fps' 处理帧率）
            tracks: 当前帧全部 tracks（bbox 应与 image 同坐标系）
            scale : 坐标缩放因子（当 image 已缩放、但 polygon 仍为原坐标时使用）
        原地绘制，返回同一图像。
        """
        # ---- 1) 每个目标：细框 + 状态标签（tracks 已与 image 同坐标）----
        for t in tracks:
            tid = t.get('track_id', -1)
            if tid is None or tid < 0:
                continue
            x1, y1, x2, y2 = t['bbox']
            color = class_color(t.get('class_id', 0))
            cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, 1)
            # 标签：区域内显 "#id 置信度 停留时间"；区域外只显置信度
            st = self._track_status.get(tid)
            conf = t.get('confidence', 0.0)
            if st is not None and st['inside']:
                label = f"#{tid} {conf:.2f} {st['dwell']:.1f}s"
            else:
                label = f"{conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image,
                         (int(x1), int(y1) - th - 6),
                         (int(x1) + tw + 4, int(y1) - 2),
                         color, -1)
            cv2.putText(image, label, (int(x1) + 2, int(y1) - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # ---- 2) 区域多边形：半透明填充 + 实线边框（按 scale 缩放）----
        # 拥堵判定：区域内数量 > 阈值 → 红色提示；否则绿色
        congested = stats['current_inside'] > self.congestion_threshold
        if self._contour is not None:
            contour = self._contour if scale == 1.0 else (
                self._contour.astype(np.float32) * scale).astype(np.int32)
            fill_bgr = (0, 0, 200) if congested else (0, 200, 0)   # 拥堵红 / 正常绿
            line_bgr = (0, 0, 255) if congested else (0, 255, 0)
            overlay = image.copy()
            cv2.fillPoly(overlay, [contour], fill_bgr)
            cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)
            cv2.polylines(image, [contour], True, line_bgr, 2)

        # ---- 4) 左上角仅显示 FPS 信息 ----
        fps_val = stats.get('fps', 0.0)
        label = f"FPS: {fps_val:.1f}"
        font, fscale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        (tw, th), _ = cv2.getTextSize(label, font, fscale, thickness)
        cv2.rectangle(image, (10, 10), (10 + tw + 16, 10 + th + 14), (0, 0, 0), -1)
        cv2.putText(image, label, (18, 10 + th + 4), font, fscale,
                    (0, 255, 255), thickness)
        return image

    def _draw_legend(self, image):
        """左下角绘制类别图例（颜色色块 + 类别名）。"""
        # 收集当前帧涉及的类别（来自 class_names；若无则跳过）
        if not self.class_names:
            return
        items = [(cid, name) for cid, name in self.class_names.items()]
        if not items:
            return
        font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
        line_h = 26
        max_text_w = max(cv2.getTextSize(name, font, scale, thickness)[0][0]
                         for _, name in items)
        box_w = max_text_w + 40   # 色块 20 + 间距 10 + 文本 + 右边距 10
        box_h = line_h * len(items) + 15
        h_img = image.shape[0]
        x0, y0 = 10, h_img - box_h - 10   # 左下角，留 10px 底边距
        # 半透明黑底
        overlay = image.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, image, 0.4, 0, image)
        for i, (cid, name) in enumerate(items):
            y = y0 + 10 + i * line_h + 18
            color = class_color(cid)
            # 色块
            cv2.rectangle(image, (x0 + 10, y - 14), (x0 + 30, y + 2), color, -1)
            # 类别名
            cv2.putText(image, str(name), (x0 + 38, y), font, scale,
                        (255, 255, 255), thickness)
        return image
