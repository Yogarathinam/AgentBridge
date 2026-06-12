from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

STYLE = """
QMainWindow {
    background-color: #0b0d12;
}
QFrame#MainPanel, QFrame#AdvPanel {
    background-color: #13161f;
    border: 1px solid #222634;
    border-radius: 12px;
}
QFrame#HeaderFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e2230, stop:1 #13161f);
    border-radius: 8px;
    border-top: 2px solid #3b82f6;
}
QLabel { color: #f8fafc; font-family: 'Segoe UI', Inter, sans-serif; }
QLabel#Title { font-size: 16px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; }
QLabel#Subtitle { font-size: 10px; color: #64748b; background: transparent; }

QPushButton#ServiceBtn {
    background-color: #3b82f6;
    color: white;
    font-weight: bold;
    font-size: 13px;
    border-radius: 8px;
    padding: 10px;
}
QPushButton#ServiceBtn:hover { background-color: #2563eb; }
QPushButton#ServiceBtn:disabled { background-color: #1e3a8a; color: #94a3b8; }

QPushButton#ServiceBtnStop {
    background-color: #ef4444;
    color: white;
    font-weight: bold;
    font-size: 13px;
    border-radius: 8px;
    padding: 10px;
}
QPushButton#ServiceBtnStop:hover { background-color: #dc2626; }
QPushButton#ServiceBtnStop:disabled { background-color: #7f1d1d; color: #94a3b8; }

QPushButton#ToolbarBtn {
    background-color: #1e2230;
    color: #cbd5e1;
    border: 1px solid #2d3345;
    border-radius: 6px;
    padding: 8px;
    font-size: 10px;
    font-weight: bold;
}
QPushButton#ToolbarBtn:hover { background-color: #272c3d; color: white; }
QPushButton#ToolbarBtn:disabled { color: #475569; border-color: #1e2230; }

QPushButton#DestructiveBtn {
    background-color: #7f1d1d;
    color: #f8fafc;
    border: 1px solid #991b1b;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 9px;
    font-weight: bold;
}
QPushButton#DestructiveBtn:hover { background-color: #991b1b; }
QPushButton#DestructiveBtn:disabled { background-color: #450a0a; color: #94a3b8; }

QFrame#InnerPanel {
    background-color: #1e2230;
    border-radius: 8px;
}

QTextEdit, QLineEdit {
    background-color: #0b0d12;
    color: #e2e8f0;
    border: 1px solid #2d3345;
    border-radius: 6px;
    padding: 8px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 10px;
}
QTextEdit:focus, QLineEdit:focus { border: 1px solid #3b82f6; }
"""

class AgentBridgeWindow(QMainWindow):
    def __init__(self, runtime) -> None:
        super().__init__()
        self.runtime = runtime
        self.setWindowTitle('AgentBridge')
        self.setStyleSheet(STYLE)
        self.is_advanced_open = False
        self.is_busy = False
        self._build_ui()
        self.setFixedWidth(380)
        self.setMinimumHeight(560)
        self.resize(380, 560)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        if self.runtime:
            self.timer.start(1000)
            self.refresh()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_h_layout = QHBoxLayout(central_widget)
        main_h_layout.setContentsMargins(12, 12, 12, 12)
        main_h_layout.setSpacing(12)

        self.main_panel = QFrame()
        self.main_panel.setObjectName("MainPanel")
        self.main_panel.setFixedWidth(356)

        layout = QVBoxLayout(self.main_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel('AgentBridge')
        title.setObjectName('Title')
        title.setStyleSheet("background: transparent;")
        subtitle = QLabel('Gemini bridge • WS Ready')
        subtitle.setObjectName('Subtitle')
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.badge = QLabel('OFFLINE')
        self.badge.setStyleSheet(
            "color: #94a3b8; font-size: 8px; font-weight: 800; "
            "background-color: #1e293b; border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px;"
        )
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addWidget(self.badge)
        layout.addWidget(self.header_frame)

        self.service_btn = QPushButton('Start Server')
        self.service_btn.setObjectName('ServiceBtn')
        self.service_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.service_btn.clicked.connect(self.toggle_service)
        layout.addWidget(self.service_btn)

        stats_layout = QHBoxLayout()

        clients_box = QVBoxLayout()
        clients_lbl = QLabel('ACTIVE CLIENTS')
        clients_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 9px; letter-spacing: 0.5px;")
        self.clients_val = QLabel('0')
        self.clients_val.setStyleSheet("color: white; font-size: 24px; font-weight: bold; font-family: Consolas;")
        clients_box.addWidget(clients_lbl)
        clients_box.addWidget(self.clients_val)

        request_box = QVBoxLayout()
        request_header = QHBoxLayout()
        request_lbl = QLabel('REQUEST STATUS')
        request_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 9px; letter-spacing: 0.5px;")
        self.request_val = QLabel('Idle')
        self.request_val.setStyleSheet("color: #cbd5e1; font-size: 10px; font-family: Consolas; font-weight: bold;")
        request_header.addWidget(request_lbl)
        request_header.addStretch()
        request_header.addWidget(self.request_val)

        self.request_bar = QProgressBar()
        self.request_bar.setTextVisible(False)
        self.request_bar.setRange(0, 1)
        self.request_bar.setValue(0)
        self.request_bar.setFixedHeight(6)
        self.request_bar.setStyleSheet("""
            QProgressBar { background-color: #1e2230; border-radius: 3px; border: none; }
            QProgressBar::chunk { background-color: #3b82f6; border-radius: 3px; }
        """)
        request_box.addLayout(request_header)
        request_box.addWidget(self.request_bar)

        stats_layout.addLayout(clients_box, 1)
        stats_layout.addSpacing(24)
        stats_layout.addLayout(request_box, 2)
        layout.addLayout(stats_layout)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.auth_btn = QPushButton('Authenticate')
        self.auth_btn.setObjectName('ToolbarBtn')
        self.auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auth_btn.clicked.connect(self.authenticate_action)

        new_chat_btn = QPushButton('New Chat')
        new_chat_btn.setObjectName('ToolbarBtn')
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.clicked.connect(self.new_chat)

        self.adv_btn = QPushButton('Advanced ⏵')
        self.adv_btn.setObjectName('ToolbarBtn')
        self.adv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adv_btn.clicked.connect(self.toggle_advanced)

        toolbar.addWidget(self.auth_btn)
        toolbar.addWidget(new_chat_btn)
        toolbar.addWidget(self.adv_btn)
        layout.addLayout(toolbar)

        status_panel = QFrame()
        status_panel.setObjectName('InnerPanel')
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(10)
        self.server_lbl = self._add_status_row(status_layout, 'Server Status', 'Stopped', '#94a3b8')
        self.auth_lbl = self._add_status_row(status_layout, 'Auth State', 'Not logged in', '#94a3b8')
        self.port_lbl = self._add_status_row(status_layout, 'Port', '-', '#f8fafc')
        self.chat_lbl = self._add_status_row(status_layout, 'Chat URL', 'No chat yet', '#f8fafc')
        layout.addWidget(status_panel)
        layout.addStretch()

        main_h_layout.addWidget(self.main_panel)

        self.adv_panel = QFrame()
        self.adv_panel.setObjectName('AdvPanel')
        self.adv_panel.setFixedWidth(380)

        adv_layout = QVBoxLayout(self.adv_panel)
        adv_layout.setContentsMargins(16, 16, 16, 16)
        adv_layout.setSpacing(14)

        utils_layout = QHBoxLayout()
        self.test_mode = QCheckBox('TEST MODE')
        self.test_mode.setChecked(True)
        self.test_mode.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 10px;")

        open_gemini_btn = QPushButton('Open Gemini UI')
        open_gemini_btn.setStyleSheet(
            "background-color: #1e2230; color: #f8fafc; border: 1px solid #2d3345; "
            "padding: 6px 12px; border-radius: 6px; font-size: 9px; font-weight: bold;"
        )
        open_gemini_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_gemini_btn.clicked.connect(self.open_gemini)

        self.clear_btn = QPushButton('Clear Session')
        self.clear_btn.setObjectName('DestructiveBtn')
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_session)

        utils_layout.addWidget(self.test_mode)
        utils_layout.addStretch()
        utils_layout.addWidget(open_gemini_btn)
        utils_layout.addWidget(self.clear_btn)
        adv_layout.addLayout(utils_layout)

        grid = QGridLayout()
        grid.setSpacing(10)

        guide_lbl = QLabel('ONBOARDING GUIDE')
        guide_lbl.setStyleSheet("color: #64748b; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        self.guide = QTextEdit()
        self.guide.setReadOnly(True)
        self.guide.setFixedHeight(85)

        error_lbl = QLabel('STATUS / ERROR')
        error_lbl.setStyleSheet("color: #64748b; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setFixedHeight(85)
        self.info_box.setStyleSheet(self.info_box.styleSheet() + "; color: #f43f5e;")

        grid.addWidget(guide_lbl, 0, 0)
        grid.addWidget(self.guide, 1, 0)
        grid.addWidget(error_lbl, 0, 1)
        grid.addWidget(self.info_box, 1, 1)
        adv_layout.addLayout(grid)

        chat_lbl = QLabel('BUILT-IN TEST CHAT')
        chat_lbl.setStyleSheet("color: #64748b; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        adv_layout.addWidget(chat_lbl)

        chat_input_layout = QHBoxLayout()
        self.prompt_box = QLineEdit()
        self.prompt_box.setPlaceholderText('Ask Gemini...')
        self.send_btn = QPushButton('Send')
        self.send_btn.setStyleSheet(
            "background-color: #3b82f6; color: white; padding: 8px 16px; "
            "border-radius: 6px; font-weight: bold; font-size: 10px;"
        )
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_test_prompt)

        chat_input_layout.addWidget(self.prompt_box)
        chat_input_layout.addWidget(self.send_btn)
        adv_layout.addLayout(chat_input_layout)

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setFixedHeight(100)
        adv_layout.addWidget(self.chat_box)

        log_lbl = QLabel('DEBUG LOG')
        log_lbl.setStyleSheet("color: #64748b; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        adv_layout.addWidget(log_lbl)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        adv_layout.addWidget(self.log_box)

        main_h_layout.addWidget(self.adv_panel)
        self.adv_panel.setVisible(False)

    def _add_status_row(self, parent_layout, label_text, value_text, val_color):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        val = QLabel(value_text)
        val.setStyleSheet(f"color: {val_color}; font-size: 11px; font-family: Consolas; font-weight: bold;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        row.addWidget(val)
        parent_layout.addLayout(row)
        return val

    def set_loading_state(self, btn, text, enabled=False):
        btn.setText(text)
        btn.setEnabled(enabled)
        QApplication.processEvents()

    def _update_guide_text(self, status):
        last_info = status.get('last_info', '')
        if 'Profile cleared' in last_info:
            self.guide.setPlainText("Session wiped successfully.\n\nRestart the service to create a fresh session.")
        elif status.get('logged_in'):
            self.guide.setPlainText("System Ready.\n\nUse your extension or the test chat below to prompt Gemini.")
        else:
            self.guide.setPlainText("1. Click Start Server.\n2. Click Authenticate.\n3. Sign in to Gemini in browser.\n4. Connect extension.\n\n* Clear Session deletes profile.")

    def toggle_service(self):
        if not self.runtime:
            return
        running = bool(self.runtime.state.get_status().get('server_running'))
        try:
            if running:
                self.set_loading_state(self.service_btn, 'Stopping...', False)
                self.runtime.gemini_loop.run(self.runtime.stop_service())
                self.runtime.log('Stop server requested from UI')
            else:
                self.set_loading_state(self.service_btn, 'Starting...', False)
                self.runtime.gemini_loop.run(self.runtime.start_service())
                self.runtime.log('Start server requested from UI')
        finally:
            self.service_btn.setEnabled(True)
            self.refresh()

    def clear_session(self):
        if not self.runtime:
            return
        reply = QMessageBox.question(
            self, 'Clear Session',
            'This will close the browser and permanently delete your saved session profile. Continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.set_loading_state(self.clear_btn, 'Clearing...', False)
            self.runtime.clear_profile()
            self.clear_btn.setEnabled(True)
            self.clear_btn.setText('Clear Session')
            self.refresh()

    def authenticate_action(self):
        if not self.runtime:
            return
        self.set_loading_state(self.auth_btn, 'Checking...', False)
        try:
            status = self.runtime.state.get_status()
            if status.get('logged_in'):
                self._run_coro(self.runtime.gemini_worker.check_login(), show_error=True)
            else:
                self._run_coro(self.runtime.gemini_worker.open_login(), show_error=True)
        finally:
            self.auth_btn.setEnabled(True)
            self.refresh()

    def toggle_advanced(self):
        self.is_advanced_open = not self.is_advanced_open
        self.adv_panel.setVisible(self.is_advanced_open)
        if self.is_advanced_open:
            self.adv_btn.setText('Advanced ⏴')
            self.adv_btn.setStyleSheet("background-color: #272c3d; color: #3b82f6;")
            self.setFixedWidth(380 + 380 + 12 + 24)
        else:
            self.adv_btn.setText('Advanced ⏵')
            self.adv_btn.setStyleSheet("")
            self.setFixedWidth(380)

    def refresh(self) -> None:
        if not self.runtime:
            return

        status = self.runtime.state.get_status()
        logged_in = bool(status.get('logged_in'))
        server_running = bool(status.get('server_running'))
        busy = bool(status.get('busy'))

        self.clients_val.setText(str(status.get('connected_clients', 0)))

        if busy:
            self.request_val.setText('Working...')
            self.request_bar.setRange(0, 0)
        else:
            self.request_val.setText('Idle')
            self.request_bar.setRange(0, 1)
            self.request_bar.setValue(0)

        self.port_lbl.setText(str(status.get('current_port') or '-'))

        chat_url = status.get('current_chat_url')
        self.chat_lbl.setText('Active' if chat_url else 'None')

        if server_running and logged_in:
            self.badge.setText('OPERATIONAL')
            self.badge.setStyleSheet("color: #10b981; font-size: 8px; font-weight: 800; background-color: #064e3b; border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px;")
        elif server_running:
            self.badge.setText('AUTH NEEDED')
            self.badge.setStyleSheet("color: #f59e0b; font-size: 8px; font-weight: 800; background-color: #78350f; border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px;")
        else:
            self.badge.setText('OFFLINE')
            self.badge.setStyleSheet("color: #94a3b8; font-size: 8px; font-weight: 800; background-color: #1e293b; border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px;")

        if server_running:
            self.service_btn.setText('Stop Server')
            self.service_btn.setObjectName('ServiceBtnStop')
            self.server_lbl.setText('Running')
            self.server_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas; font-weight: bold;")
        else:
            self.service_btn.setText('Start Server')
            self.service_btn.setObjectName('ServiceBtn')
            self.server_lbl.setText('Stopped')
            self.server_lbl.setStyleSheet("color: #f43f5e; font-size: 11px; font-family: Consolas; font-weight: bold;")

        self.service_btn.style().unpolish(self.service_btn)
        self.service_btn.style().polish(self.service_btn)

        if logged_in:
            self.auth_lbl.setText('Logged In')
            self.auth_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas; font-weight: bold;")
            self.auth_btn.setText('Verify Login')
        else:
            self.auth_lbl.setText('Auth Required')
            self.auth_lbl.setStyleSheet("color: #f43f5e; font-size: 11px; font-family: Consolas; font-weight: bold;")
            self.auth_btn.setText('Authenticate')
            
        self._update_guide_text(status)

        info = status.get('last_error') or status.get('last_info') or '> Idle. No errors detected.'
        self.info_box.setPlainText(info)

        msgs = self.runtime.state.get_messages()
        self.chat_box.setPlainText('\n'.join([f"[{m['role'].upper()}] {m['text']}" for m in msgs[-20:]]))
        self.log_box.setPlainText('\n'.join(self.runtime.logs[-50:]))

    def send_test_prompt(self):
        if not self.runtime:
            return
        prompt = self.prompt_box.text().strip()
        if not prompt:
            QMessageBox.warning(self, 'AgentBridge', 'Prompt is empty.')
            return

        self.prompt_box.clear()
        self.prompt_box.setEnabled(False)
        self.set_loading_state(self.send_btn, 'Sending...', False)
        self.runtime.state.update_status(busy=True, last_info='Sending test prompt...')
        self.runtime.log(f'Test prompt: {prompt[:50]}')
        self.refresh()

        try:
            self._run_coro(self.runtime.ask_from_ui(prompt), show_error=True)
        finally:
            self.runtime.state.update_status(busy=False)
            self.prompt_box.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.send_btn.setText('Send')
            self.refresh()

    def new_chat(self):
        if self.runtime:
            self._run_coro(self.runtime.gemini_worker.new_chat(), show_error=True)

    def open_gemini(self):
        if self.runtime:
            self._run_coro(self.runtime.gemini_worker.open_gemini(), show_error=True)

    def _run_coro(self, coro, show_error: bool):
        try:
            result = self.runtime.gemini_loop.run(coro)
            self.refresh()
            return result
        except Exception as exc:
            message = str(exc)
            self.runtime.state.update_status(last_error=message, last_info='')
            self.runtime.log(f'ERROR: {message}')
            if show_error:
                QMessageBox.critical(self, 'Error', message)
            self.refresh()
            return None