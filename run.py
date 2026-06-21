import sys
import ctypes

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.bootstrap import bootstrap_app
from app.utils import resource_path


if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "AgentBridge.AgentBridge.1"
        )
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AgentBridge")

    icon_path = resource_path("logo.ico")

    app.setWindowIcon(QIcon(icon_path))

    runtime = bootstrap_app()

    if runtime.window:
        runtime.window.setWindowIcon(QIcon(icon_path))
        runtime.window.show()

    exit_code = app.exec()

    try:
        runtime.shutdown()
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()