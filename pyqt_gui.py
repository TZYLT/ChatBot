from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QLabel, QLineEdit,
                             QGroupBox, QCheckBox, QStatusBar, QMessageBox,
                             QSplitter, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont
import logger
import os
import json
import logging
from datetime import datetime

# ---------- 自定义日志处理器（线程安全） ----------
class QtLogHandler(logging.Handler, QObject):
    """将日志记录发送到 GUI 的处理器"""
    log_signal = pyqtSignal(str, str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter(
            '[%(levelname)s][%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))

    def emit(self, record):
        """重写 emit，发射信号到主线程"""
        msg = self.format(record)
        self.log_signal.emit(record.levelname, msg)


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
        self.log_history = []  # 存储所有日志历史（用于等级过滤）
        self.init_ui()
        self.bind_signals()
        self.init_history_file()
        self.load_history()
        self.setup_logging()          # 添加日志处理器
        logger.logger.info("PyQt5 GUI 初始化完成")

    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("ChatBot")
        self.resize(1200, 700)        # 加宽窗口容纳右侧日志面板
        self.setFont(QFont("Microsoft YaHei", 11))

        # 主分割器：左侧聊天区，右侧日志区
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        # 左侧：原有聊天主界面
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.setup_chat_display(left_layout)
        self.setup_input_area(left_layout)
        self.setup_control_panel(left_layout)
        self.setup_status_bar()       # 状态栏仍放在主窗口底部，不在分割器中

        # 右侧：日志面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        # 日志等级选择栏
        log_ctrl_layout = QHBoxLayout()
        log_ctrl_layout.addWidget(QLabel("日志等级:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        log_ctrl_layout.addWidget(self.log_level_combo)
        log_ctrl_layout.addStretch()
        right_layout.addLayout(log_ctrl_layout)

        # 日志显示文本框（修复自动换行）
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)  # 自动换行
        self.log_text.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.log_text)

        # 将左右部件添加到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([700, 500])   # 初始比例

        # 状态栏单独设置
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ---------- 原有UI组件创建方法保持不变 ----------
    def setup_chat_display(self, parent_layout):
        self.chat_text = QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setLineWrapMode(QTextEdit.WidgetWidth)
        parent_layout.addWidget(self.chat_text)

    def setup_input_area(self, parent_layout):
        layout = QHBoxLayout()
        self.user_input = QTextEdit()
        self.user_input.setFixedHeight(100)
        self.send_btn = QPushButton("发送")
        layout.addWidget(self.user_input)
        layout.addWidget(self.send_btn)
        parent_layout.addLayout(layout)

    def setup_control_panel(self, parent_layout):
        layout = QHBoxLayout()

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

        display_group = QGroupBox("显示与音频设置")
        display_layout = QHBoxLayout(display_group)
        self.generate_audio = QCheckBox("生成日语语音")
        self.show_bilingual = QCheckBox("显示中日双语")
        display_layout.addWidget(self.generate_audio)
        display_layout.addWidget(self.show_bilingual)

        layout.addWidget(param_group)
        layout.addWidget(display_group)
        parent_layout.addLayout(layout)

    # 注意：setup_status_bar 已在 init_ui 中直接创建，此方法可删除或留空
    def setup_status_bar(self):
        pass

    def bind_signals(self):
        self.send_btn.clicked.connect(self.message_handler.send_message)
        self.set_context_btn.clicked.connect(self.message_handler.set_max_context)
        self.set_temp_btn.clicked.connect(self.message_handler.set_temperature)
        self.process_auto_message_signal.connect(self.message_handler.process_auto_message)
        self.add_message_signal.connect(self._add_message_ui)
        self.show_error_signal.connect(self._show_error_ui)
        self.show_info_signal.connect(self._show_info_ui)
        self.set_status_signal.connect(self._set_status_ui)
        # 日志等级变更信号
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)

        # 回车发送
        self.user_input.keyPressEvent = self.user_input_key_event

    def user_input_key_event(self, event):
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.message_handler.send_message()
        else:
            QTextEdit.keyPressEvent(self.user_input, event)

    # ---------- 日志功能 ----------
    def setup_logging(self):
        """将自定义日志处理器添加到全局 logger"""
        self.log_handler = QtLogHandler()
        # 初始等级与下拉框一致
        level = getattr(logging, self.log_level_combo.currentText(), logging.INFO)
        self.log_handler.setLevel(level)
        # 添加到 logger（避免重复添加）
        logger.logger.addHandler(self.log_handler)
        # 连接信号到显示槽函数
        self.log_handler.log_signal.connect(self.append_log)

    def change_log_level(self, level_name):
        """用户切换日志等级时更新 handler 并刷新历史日志"""
        level = getattr(logging, level_name, logging.INFO)
        self.log_handler.setLevel(level)
        self.set_status(f"日志等级已切换至 {level_name}")

        # 清空日志框，重新过滤渲染历史日志
        self.log_text.clear()
        for log in self.log_history:
            msg_level_num = getattr(logging, log["level"])
            if msg_level_num >= level:
                self.log_text.append(log["msg"])
        
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_log(self, level, msg):
        """保存日志历史，并根据当前等级过滤显示"""
        # 存储所有日志
        self.log_history.append({"level": level, "msg": msg})
        
        # 过滤显示
        current_level = self.log_handler.level
        msg_level = getattr(logging, level)
        if msg_level >= current_level:
            self.log_text.append(msg)
            # 自动滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    # ---------- 原有对外接口 ----------
    def add_message(self, sender, msg, is_user):
        self.add_message_signal.emit(sender, msg, is_user)

    def show_error(self, msg):
        self.show_error_signal.emit(msg)

    def show_info(self, msg):
        self.show_info_signal.emit(msg)

    def set_status(self, msg):
        self.set_status_signal.emit(msg)

    def toggle_widgets_state(self, enabled):
        widgets = [self.user_input, self.send_btn, self.max_context_var,
                   self.set_context_btn, self.temperature_var, self.set_temp_btn]
        for w in widgets:
            w.setEnabled(enabled)

    # ---------- 内部UI实现 ----------
    def _display_message_ui(self, sender, message, is_user):
        color = "blue" if is_user else "green"
        self.chat_text.append(f'<span style="color:{color};font-weight:bold">{sender}:</span>')
        self.chat_text.append(message + "\n")

    def _add_message_ui(self, sender, message, is_user):
        self._display_message_ui(sender, message, is_user)
        self._save_to_history(sender, message, is_user)

    def _show_error_ui(self, msg):
        QMessageBox.critical(self, "错误", msg)

    def _show_info_ui(self, msg):
        QMessageBox.information(self, "信息", msg)

    def _set_status_ui(self, msg):
        self.status_bar.showMessage(msg)

    # ---------- 历史记录 ----------
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
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            for item in history:
                self._display_message_ui(item["sender"], item["message"], item["is_user"])
        except:
            pass

    def closeEvent(self, event):
        """窗口关闭时移除日志处理器，避免重复添加"""
        logger.logger.removeHandler(self.log_handler)
        self.log_handler.close()
        event.accept()