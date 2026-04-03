from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QLabel, QLineEdit,
                             QGroupBox, QCheckBox, QStatusBar, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont
import logger
import os
import json
from datetime import datetime

class ChatGUI(QMainWindow):
    # 线程安全信号
    add_message_signal = pyqtSignal(str, str, bool)
    show_error_signal = pyqtSignal(str)
    show_info_signal = pyqtSignal(str)
    set_status_signal = pyqtSignal(str)
    process_auto_message_signal = pyqtSignal()

    def __init__(self, message_handler):
        super().__init__()
        self.message_handler = message_handler
        self.history_file = "chat_history.json"
        self.init_ui()
        self.bind_signals()
        self.init_history_file()
        self.load_history()
        logger.logger.info("PyQt5 GUI 初始化完成")

    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("ChatBot")
        self.resize(1000, 700)
        self.setFont(QFont("Microsoft YaHei", 11))

        # 主部件与布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(5)

        # 聊天显示区域
        self.setup_chat_display(main_layout)
        # 输入区域
        self.setup_input_area(main_layout)
        # 控制面板
        self.setup_control_panel(main_layout)
        # 状态栏
        self.setup_status_bar()

    def setup_chat_display(self, parent_layout):
        """聊天显示区域"""
        self.chat_text = QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setLineWrapMode(QTextEdit.WidgetWidth)
        parent_layout.addWidget(self.chat_text)

    def setup_input_area(self, parent_layout):
        """用户输入区域"""
        layout = QHBoxLayout()
        self.user_input = QTextEdit()
        self.user_input.setFixedHeight(100)
        self.send_btn = QPushButton("发送")
        layout.addWidget(self.user_input)
        layout.addWidget(self.send_btn)
        parent_layout.addLayout(layout)

    def setup_control_panel(self, parent_layout):
        """控制面板"""
        layout = QHBoxLayout()

        # AI参数面板
        param_group = QGroupBox("AI参数设置")
        param_layout = QHBoxLayout(param_group)
        param_layout.addWidget(QLabel("最大上下文:"))
        self.max_context_var = QLineEdit()
        self.max_context_var.setFixedWidth(60)
        self.set_context_btn = QPushButton("设置")
        param_layout.addWidget(self.max_context_var)
        param_layout.addWidget(self.set_context_btn)
        param_layout.addWidget(QLabel("温度参数:"))
        self.temperature_var = QLineEdit()
        self.temperature_var.setFixedWidth(60)
        self.set_temp_btn = QPushButton("设置")
        param_layout.addWidget(self.temperature_var)
        param_layout.addWidget(self.set_temp_btn)

        # 显示设置面板
        display_group = QGroupBox("显示与音频设置")
        display_layout = QHBoxLayout(display_group)
        self.generate_audio = QCheckBox("生成日语语音")
        self.show_bilingual = QCheckBox("显示中日双语")
        display_layout.addWidget(self.generate_audio)
        display_layout.addWidget(self.show_bilingual)

        layout.addWidget(param_group)
        layout.addWidget(display_group)
        parent_layout.addLayout(layout)

    def setup_status_bar(self):
        """状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def bind_signals(self):
        """绑定信号槽"""
        # 按钮绑定
        self.send_btn.clicked.connect(self.message_handler.send_message)
        self.set_context_btn.clicked.connect(self.message_handler.set_max_context)
        self.set_temp_btn.clicked.connect(self.message_handler.set_temperature)
        # 自动消息信号
        self.process_auto_message_signal.connect(self.message_handler.process_auto_message)
        # 线程安全UI信号
        self.add_message_signal.connect(self._add_message_ui)
        self.show_error_signal.connect(self._show_error_ui)
        self.show_info_signal.connect(self._show_info_ui)
        self.set_status_signal.connect(self._set_status_ui)
        # 回车发送（无Shift）
        self.user_input.keyPressEvent = self.user_input_key_event

    def user_input_key_event(self, event):
        """回车发送消息"""
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.message_handler.send_message()
        else:
            QTextEdit.keyPressEvent(self.user_input, event)

    # ------------------- 对外接口（兼容原ChatCore）-------------------
    def add_message(self, sender, msg, is_user):
        """线程安全添加消息"""
        self.add_message_signal.emit(sender, msg, is_user)

    def show_error(self, msg):
        """线程安全错误提示"""
        self.show_error_signal.emit(msg)

    def show_info(self, msg):
        """线程安全信息提示"""
        self.show_info_signal.emit(msg)

    def set_status(self, msg):
        """线程安全设置状态栏"""
        self.set_status_signal.emit(msg)

    def toggle_widgets_state(self, enabled):
        """启用/禁用控件"""
        widgets = [self.user_input, self.send_btn, self.max_context_var,
                   self.set_context_btn, self.temperature_var, self.set_temp_btn]
        for w in widgets:
            w.setEnabled(enabled)

    # ------------------- 内部UI实现（主线程执行）-------------------
    def _display_message_ui(self, sender, message, is_user):
        """【纯显示方法】仅展示消息，不保存历史（修复重复保存核心）"""
        color = "blue" if is_user else "green"
        self.chat_text.append(f'<span style="color:{color};font-weight:bold">{sender}:</span>')
        self.chat_text.append(message + "\n")

    def _add_message_ui(self, sender, message, is_user):
        """主线程添加新消息：显示 + 保存历史"""
        self._display_message_ui(sender, message, is_user)
        self._save_to_history(sender, message, is_user)  # 仅新消息保存

    def _show_error_ui(self, msg):
        QMessageBox.critical(self, "错误", msg)

    def _show_info_ui(self, msg):
        QMessageBox.information(self, "信息", msg)

    def _set_status_ui(self, msg):
        self.status_bar.showMessage(msg)

    # ------------------- 历史记录 -------------------
    def init_history_file(self):
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _save_to_history(self, sender, msg, is_user):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": msg,
            "is_user": is_user
        })
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def load_history(self):
        """加载历史：仅显示，不保存"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            for item in history:
                # 调用纯显示方法，不触发保存
                self._display_message_ui(item["sender"], item["message"], item["is_user"])
        except:
            pass