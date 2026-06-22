from __future__ import annotations

import os
import asyncio
from PyQt6.QtCore import QTimer, Qt, QUrl, QPropertyAnimation, QEasingCurve, QRect, QRectF
from PyQt6.QtGui import QDesktopServices, QPixmap, QPainter, QPainterPath, QColor
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
    QGraphicsBlurEffect,
    QGraphicsScene,
    QGraphicsPixmapItem
)

from app.config import APP_VERSION, WEB_URL
from app.utils import resource_path

STYLE = """
QMainWindow {
    background-color: transparent;
}

QFrame#CentralWidget {
    background-color: transparent;
    border: none;
}

/* Glassmorphism styling with higher transparency */
QFrame#MainPanel, QFrame#AdvPanel {
    background-color: rgba(20, 24, 34, 130);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 12px;
}

QFrame#HeaderFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 255, 255, 20), stop:1 rgba(255, 255, 255, 5));
    border-radius: 8px;
    border-top: 1px solid rgba(255, 255, 255, 50);
    border-bottom: 1px solid rgba(0, 0, 0, 30);
}

/* SCOPED LABELS: Prevents QMessageBox text from becoming invisible white-on-white */
QFrame#CentralWidget QLabel { color: #f8fafc; font-family: 'Segoe UI', Inter, sans-serif; background: transparent; }
QLabel#Title { font-size: 16px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; }
QLabel#Subtitle { font-size: 10px; color: #cbd5e1; }

QPushButton#ServiceBtn {
    background-color: rgba(59, 130, 246, 210);
    color: white;
    font-weight: bold;
    font-size: 13px;
    border-radius: 8px;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 30);
}
QPushButton#ServiceBtn:hover { background-color: rgba(37, 99, 235, 255); }
QPushButton#ServiceBtn:disabled { background-color: rgba(30, 58, 138, 150); color: #94a3b8; }

QPushButton#ServiceBtnStop {
    background-color: rgba(239, 68, 68, 210);
    color: white;
    font-weight: bold;
    font-size: 13px;
    border-radius: 8px;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 30);
}
QPushButton#ServiceBtnStop:hover { background-color: rgba(220, 38, 38, 255); }
QPushButton#ServiceBtnStop:disabled { background-color: rgba(127, 29, 29, 150); color: #94a3b8; }

QPushButton#ToolbarBtn {
    background-color: rgba(30, 34, 48, 110);
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 25);
    border-radius: 6px;
    padding: 8px;
    font-size: 10px;
    font-weight: bold;
}
QPushButton#ToolbarBtn:hover { background-color: rgba(59, 130, 246, 180); color: white; border: 1px solid rgba(255, 255, 255, 50); }
QPushButton#ToolbarBtn:disabled { color: #475569; border-color: transparent; }

QPushButton#DestructiveBtn {
    background-color: rgba(127, 29, 29, 150);
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 25);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 9px;
    font-weight: bold;
}
QPushButton#DestructiveBtn:hover { background-color: rgba(220, 38, 38, 200); }
QPushButton#DestructiveBtn:disabled { background-color: rgba(69, 10, 10, 150); color: #94a3b8; }

QPushButton#DownloadBtn {
    background-color: #10b981;
    color: white;
    border: 1px solid rgba(255, 255, 255, 40);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 9px;
    font-weight: bold;
}
QPushButton#DownloadBtn:hover { background-color: #059669; }

QPushButton#TitleBtn {
    background: transparent;
    color: #cbd5e1;
    font-weight: bold;
    border: none;
    border-radius: 4px;
    font-size: 14px;
}
QPushButton#TitleBtn:hover {
    background: rgba(255, 255, 255, 30);
    color: white;
}
QPushButton#TitleCloseBtn {
    background: transparent;
    color: #cbd5e1;
    font-weight: bold;
    border: none;
    border-radius: 4px;
    font-size: 14px;
}
QPushButton#TitleCloseBtn:hover {
    background: #ef4444;
    color: white;
}

QFrame#InnerPanel {
    background-color: rgba(11, 13, 18, 90);
    border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 8px;
}

/* SCOPED INPUTS */
QFrame#CentralWidget QTextEdit, QFrame#CentralWidget QLineEdit {
    background-color: rgba(11, 13, 18, 120);
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 6px;
    padding: 8px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 10px;
}
QFrame#CentralWidget QTextEdit:focus, QFrame#CentralWidget QLineEdit:focus { border: 1px solid #3b82f6; background-color: rgba(11, 13, 18, 160); }
"""

class BlurBackgroundFrame(QFrame):
    def __init__(self, bg_path, parent=None):
        super().__init__(parent)
        self.bg_pixmap = QPixmap(bg_path)
        self.blurred_body = self._create_blurred(self.bg_pixmap, 20)
        self.blurred_title = self._create_blurred(self.bg_pixmap, 50)

    def _create_blurred(self, pixmap: QPixmap, radius: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pixmap)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(radius)
        item.setGraphicsEffect(blur)
        scene.addItem(item)
        res = QPixmap(pixmap.size())
        res.fill(Qt.GlobalColor.transparent)
        painter = QPainter(res)
        scene.render(painter)
        painter.end()
        return res

    def paintEvent(self, event):
        if self.bg_pixmap.isNull():
            super().paintEvent(event)
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 12, 12)
        painter.setClipPath(path)
        
        scaled_body = self.blurred_body.scaled(
            rect.size(), 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        )
        crop_x = (scaled_body.width() - rect.width()) // 2
        crop_y = (scaled_body.height() - rect.height()) // 2
        
        painter.drawPixmap(rect.topLeft(), scaled_body, QRect(crop_x, crop_y, rect.width(), rect.height()))
        
        title_rect = QRect(0, 0, rect.width(), 40)
        scaled_title = self.blurred_title.scaled(
            rect.size(), 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(title_rect.topLeft(), scaled_title, QRect(crop_x, crop_y, title_rect.width(), title_rect.height()))
        
        painter.fillRect(rect, QColor(0, 0, 0, 50))
        painter.fillRect(title_rect, QColor(255, 255, 255, 35))
        painter.fillRect(title_rect, QColor(11, 13, 18, 30))
        
        painter.setPen(QColor(255, 255, 255, 40))
        painter.drawLine(0, 40, rect.width(), 40)
        
        painter.setPen(QColor(255, 255, 255, 50))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 12, 12)
        
        painter.end()
        super().paintEvent(event)


class AgentBridgeWindow(QMainWindow):
    def __init__(self, runtime) -> None:
        super().__init__()
        self.runtime = runtime
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('AgentBridge')
        self.old_pos = None
        self.setStyleSheet(STYLE)
        
        self.is_advanced_open = False
        self.is_busy = False
        self._force_popup_shown = False
        
        self._build_ui()
        self.setFixedWidth(380)
        self.setMinimumHeight(600)
        self.resize(380, 600)

        self.anim_min = QPropertyAnimation(self, b"minimumWidth")
        self.anim_max = QPropertyAnimation(self, b"maximumWidth")
        self.anim_min.setDuration(350)
        self.anim_max.setDuration(350)
        self.anim_min.setEasingCurve(QEasingCurve.Type.OutQuart)
        self.anim_max.setEasingCurve(QEasingCurve.Type.OutQuart)
        
        self.anim_min.finished.connect(self._on_animation_finished)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        if self.runtime:
            self.timer.start(1000)
            self.refresh()

    def _build_ui(self) -> None:
        bg_path = resource_path("bg.jpg")
        central_widget = BlurBackgroundFrame(bg_path)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_v_layout = QVBoxLayout(central_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)

        title_bar = QFrame()
        title_bar.setFixedHeight(40)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        
        logo_lbl = QLabel()
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(2.0)
            logo_lbl.setPixmap(pixmap)
        else:
            logo_lbl.setText("🤖")
            
        app_title = QLabel("AgentBridge")
        app_title.setStyleSheet("font-weight: 800; font-size: 13px; color: #ffffff;")
        
        min_btn = QPushButton("—")
        min_btn.setObjectName("TitleBtn")
        min_btn.setFixedSize(32, 32)
        min_btn.clicked.connect(self.showMinimized)
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("TitleCloseBtn")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.close)
        
        tb_layout.addWidget(logo_lbl)
        tb_layout.addWidget(app_title)
        tb_layout.addStretch()
        tb_layout.addWidget(min_btn)
        tb_layout.addWidget(close_btn)
        
        main_v_layout.addWidget(title_bar)

        content_widget = QWidget()
        main_h_layout = QHBoxLayout(content_widget)
        main_h_layout.setContentsMargins(12, 0, 12, 12)
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
        subtitle = QLabel('Core Service Agent')
        subtitle.setObjectName('Subtitle')
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.badge = QLabel('OFFLINE')
        self.badge.setStyleSheet(
            "color: #cbd5e1; font-size: 8px; font-weight: 800; "
            "background-color: rgba(30, 41, 59, 180); border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px; border: 1px solid rgba(255, 255, 255, 40);"
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
        clients_lbl.setStyleSheet("color: #cbd5e1; font-weight: 700; font-size: 9px; letter-spacing: 0.5px;")
        self.clients_val = QLabel('0')
        self.clients_val.setStyleSheet("color: white; font-size: 24px; font-weight: bold; font-family: Consolas;")
        clients_box.addWidget(clients_lbl)
        clients_box.addWidget(self.clients_val)

        request_box = QVBoxLayout()
        request_header = QHBoxLayout()
        request_lbl = QLabel('REQUEST STATUS')
        request_lbl.setStyleSheet("color: #cbd5e1; font-weight: 700; font-size: 9px; letter-spacing: 0.5px;")
        self.request_val = QLabel('Idle')
        self.request_val.setStyleSheet("color: #f8fafc; font-size: 10px; font-family: Consolas; font-weight: bold;")
        request_header.addWidget(request_lbl)
        request_header.addStretch()
        request_header.addWidget(self.request_val)

        self.request_bar = QProgressBar()
        self.request_bar.setTextVisible(False)
        self.request_bar.setRange(0, 1)
        self.request_bar.setValue(0)
        self.request_bar.setFixedHeight(6)
        self.request_bar.setStyleSheet("""
            QProgressBar { background-color: rgba(30, 34, 48, 120); border-radius: 3px; border: 1px solid rgba(255, 255, 255, 20); }
            QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }
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

        self.new_chat_btn = QPushButton('New Chat')
        self.new_chat_btn.setObjectName('ToolbarBtn')
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.clicked.connect(self.new_chat)

        self.adv_btn = QPushButton('Advanced ⏵')
        self.adv_btn.setObjectName('ToolbarBtn')
        self.adv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adv_btn.clicked.connect(self.toggle_advanced)

        toolbar.addWidget(self.auth_btn)
        toolbar.addWidget(self.new_chat_btn)
        toolbar.addWidget(self.adv_btn)
        layout.addLayout(toolbar)

        status_panel = QFrame()
        status_panel.setObjectName('InnerPanel')
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(10)
        self.server_lbl = self._add_status_row(status_layout, 'Server Status', 'Stopped', '#cbd5e1')
        self.auth_lbl = self._add_status_row(status_layout, 'Auth State', 'Not logged in', '#cbd5e1')
        self.port_lbl = self._add_status_row(status_layout, 'Port', '-', '#ffffff')
        self.chat_lbl = self._add_status_row(status_layout, 'Chat URL', 'No chat yet', '#ffffff')
        self.user_lbl = self._add_status_row(status_layout, 'User', 'Not available', '#ffffff')
        self.version_lbl = self._add_status_row(status_layout, 'Version', APP_VERSION, '#ffffff')
        self._add_update_row(status_layout)
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
        self.test_mode.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 10px;")

        self.open_gemini_btn = QPushButton('Open Gemini UI')
        self.open_gemini_btn.setStyleSheet(
            "background-color: rgba(30, 34, 48, 120); color: #ffffff; border: 1px solid rgba(255, 255, 255, 40); "
            "padding: 6px 12px; border-radius: 6px; font-size: 9px; font-weight: bold;"
        )
        self.open_gemini_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_gemini_btn.clicked.connect(self.open_gemini)

        self.clear_btn = QPushButton('Clear Session')
        self.clear_btn.setObjectName('DestructiveBtn')
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_session)

        utils_layout.addWidget(self.test_mode)
        utils_layout.addStretch()
        utils_layout.addWidget(self.open_gemini_btn)
        utils_layout.addWidget(self.clear_btn)
        adv_layout.addLayout(utils_layout)

        grid = QGridLayout()
        grid.setSpacing(10)

        guide_lbl = QLabel('ONBOARDING GUIDE')
        guide_lbl.setStyleSheet("color: #cbd5e1; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        self.guide = QTextEdit()
        self.guide.setReadOnly(True)
        self.guide.setFixedHeight(85)

        error_lbl = QLabel('STATUS / ERROR')
        error_lbl.setStyleSheet("color: #cbd5e1; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setFixedHeight(85)
        self.info_box.setStyleSheet(self.info_box.styleSheet() + "; color: #f87171;")

        grid.addWidget(guide_lbl, 0, 0)
        grid.addWidget(self.guide, 1, 0)
        grid.addWidget(error_lbl, 0, 1)
        grid.addWidget(self.info_box, 1, 1)
        adv_layout.addLayout(grid)

        chat_lbl = QLabel('BUILT-IN TEST CHAT')
        chat_lbl.setStyleSheet("color: #cbd5e1; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        adv_layout.addWidget(chat_lbl)

        chat_input_layout = QHBoxLayout()
        self.prompt_box = QLineEdit()
        self.prompt_box.setPlaceholderText('Ask Gemini...')
        self.send_btn = QPushButton('Send')
        self.send_btn.setStyleSheet(
            "background-color: rgba(59, 130, 246, 210); color: white; padding: 8px 16px; "
            "border-radius: 6px; font-weight: bold; font-size: 10px; border: 1px solid rgba(255, 255, 255, 40);"
        )
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_test_prompt)

        chat_input_layout.addWidget(self.prompt_box)
        chat_input_layout.addWidget(self.send_btn)
        adv_layout.addLayout(chat_input_layout)

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setMinimumHeight(120)
        adv_layout.addWidget(self.chat_box)

        log_lbl = QLabel('DEBUG LOG')
        log_lbl.setStyleSheet("color: #cbd5e1; font-weight: 800; font-size: 9px; letter-spacing: 0.5px;")
        adv_layout.addWidget(log_lbl)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(120)
        adv_layout.addWidget(self.log_box)

        main_h_layout.addWidget(self.adv_panel)
        self.adv_panel.setVisible(False)
        
        main_v_layout.addWidget(content_widget)

    def _add_status_row(self, parent_layout, label_text, value_text, val_color):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 600;")
        val = QLabel(value_text)
        val.setStyleSheet(f"color: {val_color}; font-size: 11px; font-family: Consolas; font-weight: bold;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        row.addWidget(val)
        parent_layout.addLayout(row)
        return val

    def _add_update_row(self, parent_layout):
        row = QHBoxLayout()
        lbl = QLabel('Update')
        lbl.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 600;")
        
        self.update_lbl = QLabel('Up to date')
        self.update_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-family: Consolas; font-weight: bold;")
        self.update_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.download_btn = QPushButton('Download')
        self.download_btn.setObjectName('DownloadBtn')
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setVisible(False)
        self.download_btn.clicked.connect(self.download_update)
        
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self.update_lbl)
        row.addWidget(self.download_btn)
        parent_layout.addLayout(row)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

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
            self.guide.setPlainText(
                "1. Click Start Server.\n"
                "2. Click Authenticate.\n"
                "3. Sign in to Google in browser.\n"
                "4. Connect extension.\n\n"
                "* Clear Session deletes the saved profile and starts fresh."
            )

    def _check_force_update(self) -> bool:
        """Shields all button actions. Triggers refresh/lock if flag is active."""
        if self.runtime and self.runtime.state.get_status().get('force_update'):
            print("[UI] Action blocked: Force update flag is active. Triggering app lock.", flush=True)
            self.refresh()
            return True
        return False

    def _run_async(self, coro, btn=None, texts=None, show_error=True, on_done=None):
        self.is_busy = True
        self.refresh()
        
        future = asyncio.run_coroutine_threadsafe(coro, self.runtime.gemini_loop.loop)
        
        anim_timer = None
        if btn and texts:
            anim_state = {'ticks': 0, 'idx': 0}
            def update_anim():
                dots = "." * (anim_state['ticks'] % 4)
                current_text = texts[anim_state['idx']]
                btn.setText(f"{current_text}{dots}")
                anim_state['ticks'] += 1
                if anim_state['ticks'] % 5 == 0:
                    anim_state['idx'] = min(anim_state['idx'] + 1, len(texts) - 1)
            
            anim_timer = QTimer(self)
            anim_timer.timeout.connect(update_anim)
            anim_timer.start(300)

        poll_timer = QTimer(self)
        def check():
            if future.done():
                poll_timer.stop()
                poll_timer.deleteLater()
                if anim_timer:
                    anim_timer.stop()
                    anim_timer.deleteLater()
                
                self.is_busy = False
                
                try:
                    res = future.result()
                    if on_done: on_done(res)
                except Exception as exc:
                    msg = str(exc)
                    self.runtime.state.update_status(last_error=msg, last_info='')
                    self.runtime.log(f'ERROR: {msg}')
                    if show_error:
                        QMessageBox.critical(self, 'Error', msg)
                    if on_done: on_done(None)
                finally:
                    self.refresh()
                    
        poll_timer.timeout.connect(check)
        poll_timer.start(50)

    def toggle_service(self):
            if self._check_force_update(): return
            if not self.runtime:
                return
                
            status = self.runtime.state.get_status()
            running = bool(status.get('server_running'))
            
            # --- REMOVED THE UI INTERCEPT BLOCK HERE ---
            # We now trust the background bootstrapper to handle auto-logins

            if running:
                self.set_loading_state(self.service_btn, 'Stopping...', False)
                self.runtime.log('Stop server requested from UI')
                self._run_async(
                    self.runtime.stop_service(),
                    btn=self.service_btn,
                    texts=['Stopping service', 'Closing connections', 'Cleaning up'],
                    on_done=self._finalize_toggle
                )
            else:
                self.set_loading_state(self.service_btn, 'Starting...', False)
                self.runtime.log('Start server requested from UI')
                self._run_async(
                    self.runtime.start_service(),
                    btn=self.service_btn,
                    texts=['Checking system', 'Verifying Google account', 'Launching browser', 'Starting WebSocket'],
                    on_done=self._finalize_toggle
                )

    def _finalize_toggle(self, res=None):
        if not self.runtime.state.get_status().get('force_update'):
            self.service_btn.setEnabled(True)
        self.refresh()

    def clear_session(self):
        if self._check_force_update(): return
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
        if self._check_force_update(): return
        if not self.runtime:
            return
        self.set_loading_state(self.auth_btn, 'Opening...', False)
        status = self.runtime.state.get_status()
        if not status.get('logged_in'):
            coro = self.runtime.gemini_worker.open_login()
        else:
            coro = self.runtime.gemini_worker.check_login()
            
        self._run_async(
            coro,
            btn=self.auth_btn,
            texts=['Verifying session', 'Checking cookies', 'Opening Google Auth'],
            on_done=self._finalize_auth
        )

    def _finalize_auth(self, res=None):
        if not self.runtime.state.get_status().get('force_update'):
            self.auth_btn.setEnabled(True)
        self.refresh()

    def download_update(self):
        print("[UI] Launching download URL.", flush=True)
        QDesktopServices.openUrl(QUrl(WEB_URL))

    def toggle_advanced(self):
        if self._check_force_update(): return
        self.is_advanced_open = not self.is_advanced_open
        
        target_width = 772 if self.is_advanced_open else 380
        
        self.anim_min.setStartValue(self.width())
        self.anim_min.setEndValue(target_width)
        self.anim_max.setStartValue(self.width())
        self.anim_max.setEndValue(target_width)

        if self.is_advanced_open:
            self.adv_btn.setText('Advanced ⏴')
            self.adv_btn.setStyleSheet("background-color: rgba(59, 130, 246, 180); color: #ffffff; border: 1px solid rgba(255, 255, 255, 50);")
            self.adv_panel.setVisible(True)
        else:
            self.adv_btn.setText('Advanced ⏵')
            self.adv_btn.setStyleSheet("")
            
        self.anim_min.start()
        self.anim_max.start()

    def _on_animation_finished(self):
        if not self.is_advanced_open:
            self.adv_panel.setVisible(False)

    def show_force_update_popup(self, announcement: str, version: str):
        """Refined popup overlaying the content panel with a polished UI card."""
        print(f"[UI] Rendering in-app lock screen overlay...", flush=True)
        
        # 1. Disable only the internal panels so title bar buttons (Minimize, Close) remain active.
        self.main_panel.setDisabled(True)
        if hasattr(self, 'adv_panel'):
            self.adv_panel.setDisabled(True)

        # --- DATA SANITIZATION ---
        clean_ver = str(version) if version and str(version).lower() != 'none' else "Required"
        if not announcement or "Starting" in announcement or announcement.strip() == "":
            clean_msg = "A mandatory system update is available. This older version has been deprecated to ensure security and compatibility."
        else:
            clean_msg = announcement
        # -------------------------
        
        # 2. Create an overlay that covers everything BELOW the 40px custom title bar
        self.overlay = QFrame(self) 
        self.overlay.setGeometry(0, 40, self.width(), self.height() - 40)
        self.overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 230);
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        self.overlay.raise_() 
        self.overlay.setMouseTracking(True) # Prevent clicks from passing through
        
        # 3. Build Main Layout
        layout = QVBoxLayout(self.overlay)
        layout.setContentsMargins(24, 20, 24, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 4. Create an inner "Card" to hold the warning
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 220);
                border: 1px solid rgba(239, 68, 68, 100);
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 30, 20, 30)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 5. Build Content Inside Card
        icon = QLabel("⚠️")  # Restored the attention mark!
        # Bumped the font size up to 64px to make it stand out inside the card
        icon.setStyleSheet("font-size: 64px; background: transparent; border: none;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("UPDATE REQUIRED")
        title.setStyleSheet("color: #f87171; font-weight: 900; font-size: 16px; background: transparent; letter-spacing: 1.5px; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # We save these as "self" variables so the refresh loop can dynamically update them later!
        self.overlay_ver_label = QLabel()
        self.overlay_ver_label.setStyleSheet("color: #93c5fd; font-size: 11px; font-weight: bold; background: transparent; font-family: Consolas; border: none;")
        self.overlay_ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.overlay_msg_label = QLabel()
        self.overlay_msg_label.setStyleSheet("color: #e2e8f0; font-size: 12px; background: transparent; margin-top: 15px; border: none; line-height: 1.4;")
        self.overlay_msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_msg_label.setWordWrap(True)

        # Set initial text
        ver_text = f"Current: v{APP_VERSION}   →   Latest: v{clean_ver}" if clean_ver != "Required" else f"Current: v{APP_VERSION}   →   Update Required"
        self.overlay_ver_label.setText(ver_text)
        self.overlay_msg_label.setText(f"{clean_msg}\n\nPlease update to restore full functionality.")

        card_layout.addWidget(icon)
        card_layout.addSpacing(5)
        card_layout.addWidget(title)
        card_layout.addWidget(self.overlay_ver_label)
        card_layout.addWidget(self.overlay_msg_label)

        # 6. Button Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        close_btn = QPushButton("Quit")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 10); 
                color: #cbd5e1; 
                padding: 10px 14px; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 20);
            }
            QPushButton:hover { 
                background-color: rgba(239, 68, 68, 150); 
                color: white; 
                border-color: transparent;
            }
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)

        dl_btn = QPushButton("Download Update")
        dl_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; 
                color: white; 
                padding: 10px 14px; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
            QPushButton:hover { 
                background-color: #2563eb; 
                border: 1px solid rgba(255, 255, 255, 80); 
            }
        """)
        dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(WEB_URL)))

        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(dl_btn)
        
        # 7. Add widgets to main overlay layout
        layout.addStretch()
        layout.addWidget(card)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # 8. Render
        self.overlay.show()
        self.overlay.update()
        QApplication.processEvents()

    def refresh(self) -> None:
        if not self.runtime:
            return

        status = self.runtime.state.get_status()
        force_update = bool(status.get('force_update'))
        
        if force_update:
            # Halt background server if running
            if status.get('server_running') and not getattr(self, '_force_halt_triggered', False):
                self._force_halt_triggered = True
                print("[UI] Force update triggered. Sending aggressive halt signal to background server...", flush=True)
                self.runtime.log("Force update triggered. Halting background server...")
                asyncio.run_coroutine_threadsafe(self.runtime.stop_service(), self.runtime.gemini_loop.loop)
            
            # Check if popup is already open
            if not getattr(self, '_force_popup_shown', False):
                self._force_popup_shown = True
                print("[UI] Force update flag detected. Locking UI.", flush=True)
                
                # Disable buttons
                self.service_btn.setEnabled(False)
                self.auth_btn.setEnabled(False)
                self.new_chat_btn.setEnabled(False)
                self.adv_btn.setEnabled(False)
                self.open_gemini_btn.setEnabled(False)
                self.clear_btn.setEnabled(False)
                self.send_btn.setEnabled(False)
                self.prompt_box.setEnabled(False)
                self.download_btn.setEnabled(False)
                
                announcement = status.get('last_info', 'Update Required')
                version = status.get('latest_version', APP_VERSION)
                QTimer.singleShot(10, lambda a=announcement, v=version: self.show_force_update_popup(a, v))
            
            else:
                # DYNAMIC UPDATE: If the popup is already showing but the cloud fetch just finished, update the text!
                if hasattr(self, 'overlay_ver_label') and hasattr(self, 'overlay_msg_label'):
                    version = status.get('latest_version')
                    announcement = status.get('last_info', '')
                    
                    clean_ver = str(version) if version and str(version).lower() != 'none' else "Required"
                    ver_text = f"Current: v{APP_VERSION}   →   Latest: v{clean_ver}" if clean_ver != "Required" else f"Current: v{APP_VERSION}   →   Update Required"
                    
                    if not announcement or "Starting" in announcement or announcement.strip() == "":
                        clean_msg = "A mandatory system update is available. This older version has been deprecated to ensure security and compatibility."
                    else:
                        clean_msg = announcement
                        
                    self.overlay_ver_label.setText(ver_text)
                    self.overlay_msg_label.setText(f"{clean_msg}\n\nPlease update to restore full functionality.")
            
            # EARLY RETURN: This stops the terminal spam and freezes the background UI updates.
            return

        logged_in = bool(status.get('logged_in'))
        server_running = bool(status.get('server_running'))
        runtime_busy = bool(status.get('busy'))
        
        currently_working = self.is_busy or runtime_busy

        self.clients_val.setText(str(status.get('connected_clients', 0)))

        if currently_working:
            self.request_val.setText('Working...')
            self.request_bar.setRange(0, 0)
        else:
            self.request_val.setText('Idle')
            self.request_bar.setRange(0, 1)
            self.request_bar.setValue(0)

        self.port_lbl.setText(str(status.get('current_port') or '-'))

        chat_url = status.get('current_chat_url')
        self.chat_lbl.setText('Active' if chat_url else 'None')

        user_email = status.get('user_email') or 'Not available'
        self.user_lbl.setText(user_email)
        self.version_lbl.setText(str(status.get('latest_version') or APP_VERSION))
        
        update_available = bool(status.get('update_available'))
        self.update_lbl.setText('Update available' if update_available else 'Up to date')
        self.update_lbl.setStyleSheet(
            'color: #fbbf24; font-size: 11px; font-family: Consolas; font-weight: bold;'
            if update_available else
            'color: #34d399; font-size: 11px; font-family: Consolas; font-weight: bold;'
        )
        self.download_btn.setVisible(update_available)

        if server_running and logged_in:
            self.badge.setText('OPERATIONAL')
            self.badge.setStyleSheet("color: #34d399; font-size: 8px; font-weight: 800; background-color: rgba(6, 78, 59, 200); border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px; border: 1px solid rgba(255, 255, 255, 40);")
        elif server_running:
            self.badge.setText('AUTH NEEDED')
            self.badge.setStyleSheet("color: #fbbf24; font-size: 8px; font-weight: 800; background-color: rgba(120, 53, 15, 200); border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px; border: 1px solid rgba(255, 255, 255, 40);")
        else:
            self.badge.setText('OFFLINE')
            self.badge.setStyleSheet("color: #cbd5e1; font-size: 8px; font-weight: 800; background-color: rgba(30, 41, 59, 200); border-radius: 4px; padding: 4px 8px; letter-spacing: 0.5px; border: 1px solid rgba(255, 255, 255, 30);")

        if server_running:
            self.service_btn.setObjectName('ServiceBtnStop')
            if not self.is_busy:
                self.service_btn.setText('Stop Server')
            self.server_lbl.setText('Running')
            self.server_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-family: Consolas; font-weight: bold;")
        else:
            self.service_btn.setObjectName('ServiceBtn')
            if not self.is_busy:
                self.service_btn.setText('Start Server')
            self.server_lbl.setText('Stopped')
            self.server_lbl.setStyleSheet("color: #f87171; font-size: 11px; font-family: Consolas; font-weight: bold;")

        self.service_btn.style().unpolish(self.service_btn)
        self.service_btn.style().polish(self.service_btn)

        if logged_in:
            self.auth_lbl.setText('Logged In')
            self.auth_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-family: Consolas; font-weight: bold;")
            if not self.is_busy:
                self.auth_btn.setText('Verify Login')
        else:
            self.auth_lbl.setText('Auth Required')
            self.auth_lbl.setStyleSheet("color: #f87171; font-size: 11px; font-family: Consolas; font-weight: bold;")
            if not self.is_busy:
                self.auth_btn.setText('Authenticate')

        self._update_guide_text(status)

        info = status.get('last_error') or status.get('last_info') or '> Idle. No errors detected.'
        self.info_box.setPlainText(info)

        # --- FIX: Removed 'server_running' requirement from auth_btn and clear_btn ---
        self.service_btn.setEnabled(not self.is_busy)
        self.auth_btn.setEnabled(not currently_working) 
        self.new_chat_btn.setEnabled(server_running and not currently_working)
        self.open_gemini_btn.setEnabled(server_running and not currently_working)
        self.clear_btn.setEnabled(not currently_working)
        self.send_btn.setEnabled(server_running and logged_in and not currently_working)
        self.prompt_box.setEnabled(server_running and logged_in and not currently_working)

        msgs = self.runtime.state.get_messages()
        new_chat_text = '\n'.join([f"[{m['role'].upper()}] {m['text']}" for m in msgs[-20:]])
        if self.chat_box.toPlainText() != new_chat_text:
            self.chat_box.setPlainText(new_chat_text)
            self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())

        new_log_text = '\n'.join(self.runtime.logs[-50:])
        if self.log_box.toPlainText() != new_log_text:
            self.log_box.setPlainText(new_log_text)
            self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def send_test_prompt(self):
        if self._check_force_update(): return
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

        self._run_async(
            self.runtime.ask_from_ui(prompt),
            btn=self.send_btn,
            texts=['Sending prompt', 'Waiting for Gemini', 'Generating response'],
            on_done=self._finalize_send
        )

    def _finalize_send(self, res=None):
        self.runtime.state.update_status(busy=False)
        if not self.runtime.state.get_status().get('force_update'):
            self.prompt_box.setEnabled(True)
            self.send_btn.setEnabled(True)
        self.send_btn.setText('Send')
        self.refresh()

    def new_chat(self):
        if self._check_force_update(): return
        if self.runtime:
            self._run_async(self.runtime.gemini_worker.new_chat())

    def open_gemini(self):
        if self._check_force_update(): return
        if self.runtime:
            self._run_async(self.runtime.gemini_worker.open_gemini())