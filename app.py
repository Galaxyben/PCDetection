import sys
import threading
import os
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon
from hardware import HardwareDetector


# ---------- Signal bridge for thread -> UI communication ----------
class SignalBridge(QObject):
    finished = pyqtSignal(str, bool)   # (message, is_success)
    preview_ready = pyqtSignal(str)    # markdown content


# ---------- Stylesheet ----------
STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}
QWidget#central {
    background-color: #0d1117;
}

QLabel#title {
    color: #58a6ff;
    font-size: 28px;
    font-weight: 700;
    padding-top: 10px;
}
QLabel#subtitle {
    color: #8b949e;
    font-size: 13px;
}
QLabel#status {
    color: #8b949e;
    font-size: 12px;
    padding-bottom: 8px;
}

QPushButton#scanBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 15px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton#scanBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}
QPushButton#scanBtn:pressed {
    background-color: #196c2e;
}
QPushButton#scanBtn:disabled {
    background-color: #1a1e24;
    color: #484f58;
    border-color: #30363d;
}

QPushButton#saveBtn {
    background-color: #1f6feb;
    color: #ffffff;
    border: 1px solid #388bfd;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 15px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton#saveBtn:hover {
    background-color: #388bfd;
}
QPushButton#saveBtn:pressed {
    background-color: #1158c7;
}
QPushButton#saveBtn:disabled {
    background-color: #1a1e24;
    color: #484f58;
    border-color: #30363d;
}

QPushButton#copyBtn {
    background-color: #6e40c9;
    color: #ffffff;
    border: 1px solid #8957e5;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 15px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton#copyBtn:hover {
    background-color: #8957e5;
}
QPushButton#copyBtn:pressed {
    background-color: #553098;
}
QPushButton#copyBtn:disabled {
    background-color: #1a1e24;
    color: #484f58;
    border-color: #30363d;
}

QTextEdit#preview {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: #264f78;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCDetection — Escáner de Hardware")
        self.setMinimumSize(620, 520)
        self.resize(680, 580)

        self._markdown_content = ""
        self._bridge = SignalBridge()
        self._bridge.finished.connect(self._on_scan_finished)
        self._bridge.preview_ready.connect(self._on_preview_ready)

        # ---------- Central widget ----------
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(8)

        # Title
        title = QLabel("⚡ PCDetection")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Analiza todos los componentes de tu PC y genera un reporte Markdown.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        # Scan button
        self.scan_btn = QPushButton("🔍  Analizar Hardware")
        self.scan_btn.setObjectName("scanBtn")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start_scan)
        layout.addWidget(self.scan_btn)

        # Preview area
        self.preview = QTextEdit()
        self.preview.setObjectName("preview")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("El reporte aparecerá aquí después del análisis…")
        layout.addWidget(self.preview, stretch=1)

        # Button row (Save + Copy)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_btn = QPushButton("💾  Guardar (.md)")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_report)
        btn_row.addWidget(self.save_btn)

        self.copy_btn = QPushButton("📋  Copiar Texto")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(self.copy_btn)

        layout.addLayout(btn_row)

        # Status bar label
        self.status_label = QLabel("Listo.")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    # ---------- Scan logic ----------
    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.scan_btn.setText("⏳  Analizando…")
        self.status_label.setText("Obteniendo información del sistema…")
        self.status_label.setStyleSheet("color: #d29922;")
        self.preview.clear()

        thread = threading.Thread(target=self._run_detection, daemon=True)
        thread.start()

    def _run_detection(self):
        try:
            detector = HardwareDetector()
            md = detector.generate_markdown()
            self._bridge.preview_ready.emit(md)
            self._bridge.finished.emit("Análisis completado.", True)
        except Exception as e:
            self._bridge.finished.emit(f"Error: {e}", False)

    def _on_preview_ready(self, md: str):
        self._markdown_content = md
        self.preview.setPlainText(md)

    def _on_scan_finished(self, message: str, success: bool):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🔍  Analizar Hardware")
        if success:
            self.status_label.setStyleSheet("color: #3fb950;")
            self.save_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
        else:
            self.status_label.setStyleSheet("color: #f85149;")
        self.status_label.setText(message)

    # ---------- Save ----------
    def _save_report(self):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"Reporte_Hardware_{date_str}.md"

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte", default_name,
            "Markdown (*.md);;Todos los archivos (*)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._markdown_content)
            self.status_label.setText(f"Guardado: {os.path.basename(path)}")
            self.status_label.setStyleSheet("color: #3fb950;")
        except Exception as e:
            self.status_label.setText(f"Error al guardar: {e}")
            self.status_label.setStyleSheet("color: #f85149;")

    # ---------- Copy to Clipboard ----------
    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._markdown_content)
        self.status_label.setText("¡Copiado al portapapeles!")
        self.status_label.setStyleSheet("color: #d2a8ff;")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
