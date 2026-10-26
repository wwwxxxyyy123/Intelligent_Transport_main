"""程序入口：DPI、主题与调色板 → 预加载模型 → 启动主窗口。

模型加载（ONNX session + CUDA 初始化）耗时较长，在窗口显示前完成，
加载期间显示进度窗口。运行方式: python main.py
"""
import sys
import time

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMessageBox, QProgressBar, QVBoxLayout, QWidget,
)

from app.config import Config
from app.frontend.theme import (
    FONT_FAMILY, FONT_SIZE_BASE, PAD_CARD, PAD_SECTION,
    build_global_qss, make_app_icon,
)


def _apply_light_palette(app):
    """Fusion 风格 + 浅色调色板：让原生控件/文件对话框也跟随浅色主题。"""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#e8eef7"))
    palette.setColor(QPalette.WindowText, QColor("#17233a"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f8fafd"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#17233a"))
    palette.setColor(QPalette.Text, QColor("#17233a"))
    palette.setColor(QPalette.Button, QColor("#f6f8fc"))
    palette.setColor(QPalette.ButtonText, QColor("#17233a"))
    palette.setColor(QPalette.BrightText, QColor("#dd4b3f"))
    palette.setColor(QPalette.Link, QColor("#1d6fd4"))
    palette.setColor(QPalette.Highlight, QColor("#1d6fd4"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.PlaceholderText, QColor("#8894ab"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#8894ab"))
    app.setPalette(palette)


class LoadingWindow(QWidget):
    """启动加载进度窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("加载中")
        self.setWindowIcon(make_app_icon())
        self.setFixedSize(440, 240)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint)
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD_CARD + 8, PAD_CARD + 8, PAD_CARD + 8, PAD_CARD + 8)
        layout.setSpacing(PAD_SECTION)

        logo = QLabel()
        logo.setPixmap(make_app_icon().pixmap(56, 56))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        title = QLabel("智能交通检测系统")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._label = QLabel("正在初始化环境...")
        self._label.setObjectName("secondaryLabel")
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
        layout.addStretch()

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
    app.setApplicationName("智能交通检测系统")
    _apply_light_palette(app)

    base_font = QFont(FONT_FAMILY)
    base_font.setPointSize(FONT_SIZE_BASE)
    base_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(base_font)
    app.setStyleSheet(build_global_qss())
    app.setWindowIcon(make_app_icon())

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
