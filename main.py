"""程序入口：DPI 与全局主题 → 预加载模型 → 启动主窗口。

模型加载（ONNX session + CUDA 初始化）耗时较长，在窗口显示前完成，
加载期间显示进度窗口。运行方式: python main.py
"""
import sys
import time

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMessageBox, QProgressBar, QVBoxLayout, QWidget,
)

from app.config import Config
from app.frontend.theme import (
    FONT_FAMILY, FONT_SIZE_BASE, PAD_CARD, PAD_SECTION, build_global_qss,
)


class LoadingWindow(QWidget):
    """启动加载进度窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("加载中")
        self.setFixedSize(400, 180)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint)
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD_CARD, PAD_CARD, PAD_CARD, PAD_CARD)
        layout.setSpacing(PAD_SECTION)

        title = QLabel("智能交通检测系统")
        title.setObjectName("panelHead")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._label = QLabel("正在初始化环境...")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFormat("加载中…")
        layout.addWidget(self._progress)

        tip = QLabel("首次加载需几秒，请稍候")
        tip.setObjectName("mutedLabel")
        tip.setAlignment(Qt.AlignCenter)
        layout.addWidget(tip)

    def set_status(self, text):
        self._label.setText(text)
        QApplication.processEvents()


def _preload_detector(loading):
    """加载 Detector 并做一次 dummy 推理预热，返回 (detector, 错误信息)。"""
    import numpy as np

    from app.backend.detector import Detector
    try:
        detector = Detector()
        t0 = time.time()
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        detector.model.predict(source=dummy, imgsz=detector.image_size,
                               conf=detector.conf, iou=detector.iou,
                               save=False, verbose=False)
        print(f"[加载] 模型预热完成，耗时 {time.time() - t0:.1f}s")
        return detector, None
    except Exception as e:
        return None, f"模型加载失败：{e}"


def main():
    # 高 DPI 属性必须在 QApplication 创建之前设置
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    base_font = QFont(FONT_FAMILY)
    base_font.setPointSize(FONT_SIZE_BASE)
    base_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(base_font)
    app.setStyleSheet(build_global_qss())

    loading = LoadingWindow()
    loading.show()
    app.processEvents()

    loading.set_status("正在加载配置...")
    Config()

    loading.set_status("正在加载检测模型（首次加载约需几秒）...")
    detector, error_msg = _preload_detector(loading)

    loading.close()
    QApplication.processEvents()

    if error_msg:
        QMessageBox.critical(None, "启动失败", error_msg)
        sys.exit(1)

    from app.frontend.main_window import MainWindow
    window = MainWindow(detector=detector)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
