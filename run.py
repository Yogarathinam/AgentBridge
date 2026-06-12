import sys
from PyQt6.QtWidgets import QApplication
from app.bootstrap import bootstrap_app


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AgentBridge")
    runtime = bootstrap_app()
    runtime.window.show()
    exit_code = app.exec()
    runtime.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
