"""视频目标跟踪后端：YOLO + ByteTrack 逐帧产出跟踪结果。

    tracker = VideoTracker()
    for fr in tracker.track_video('traffic.mp4'):
        ...
    # 可在中途 break 提前终止，资源由 finally 释放
"""
from collections import namedtuple

import cv2

from app.backend.model import YOLOModel

# 单帧跟踪结果
FrameResult = namedtuple('FrameResult', [
    'frame_idx',     # 帧序号（从 0 起）
    'frame',         # 原始 BGR 图像（未绘制）
    'tracks',        # 该帧目标列表，含 track_id/class_id/class_name/confidence/bbox
    'total_frames',  # 视频总帧数（未知为 -1）
    'fps',           # 视频帧率
])


class VideoTracker(YOLOModel):
    """视频多目标跟踪器（persist=True 维持跨帧 track_id）。"""

    def __init__(self):
        super().__init__()
        self.tracker_cfg = self.config.get('tracking', 'tracker', default='bytetrack.yaml')

    def track_video(self, source, save_path=None):
        """逐帧跟踪视频，yield FrameResult。

        source 可为视频路径 / 摄像头索引 / RTSP 流；save_path 提供时写出原始帧。
        """
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频源: {source}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = None
        if save_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(save_path, fourcc, fps, (w, h))

        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                result = self.model.track(source=frame, persist=True,
                                          tracker=self.tracker_cfg,
                                          **self._infer_kwargs())[0]
                tracks = self._parse_tracks(result)
                if writer is not None:
                    writer.write(frame)
                yield FrameResult(frame_idx, frame, tracks, total, fps)
                frame_idx += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()

    @staticmethod
    def _parse_tracks(result):
        """从跟踪结果对象提取每目标信息（含 track_id，未分配时为 -1）。"""
        tracks = []
        if result.boxes is None or len(result.boxes) == 0:
            return tracks

        boxes = result.boxes.xyxy.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)
        confs = result.boxes.conf.cpu().numpy() if result.boxes.conf is not None else None
        ids = result.boxes.id.cpu().numpy().astype(int) if result.boxes.id is not None else None
        names = result.names

        for i, (x1, y1, x2, y2) in enumerate(boxes):
            tracks.append({
                'track_id': int(ids[i]) if ids is not None else -1,
                'class_id': int(cls_ids[i]),
                'class_name': str(names.get(int(cls_ids[i]), cls_ids[i])),
                'confidence': float(confs[i]) if confs is not None else 1.0,
                'bbox': [float(v) for v in (x1, y1, x2, y2)],
            })
        return tracks
