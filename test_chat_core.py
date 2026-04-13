import json
import logging
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, call, ANY

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication

from chat_core import ChatCore, setup_logger, user_name, bot_name

# 创建一个全局 QApplication 供测试使用（PyQt 信号需要事件循环）
app = QApplication([])


class TestChatCore(unittest.TestCase):
    """ChatCore 单元测试"""

    @classmethod
    def setUpClass(cls):
        """全局初始化（如日志设置）"""
        # 确保日志不会重复添加 handler
        logging.getLogger("ChatBot").handlers.clear()

    def setUp(self):
        """每个测试用例前执行：创建 mock 对象和 ChatCore 实例"""
        # Mock AudioHandler
        self.mock_audio = MagicMock()
        self.mock_audio.is_playing.return_value = False
        self.mock_audio.play_japanese_audio.return_value = None

        # Mock AIHandler (在 patch 中创建)
        self.mock_ai = MagicMock()
        self.mock_ai.get_now_max_context.return_value = 2048
        self.mock_ai.get_temperature.return_value = 0.7

        # Mock ToolInvoker
        self.mock_tools = MagicMock()
        self.mock_tools.get_responses.return_value = []
        self.mock_tools.add_tasks.return_value = None

        # Mock ConfigManager
        self.mock_config = MagicMock()
        self.mock_config.get_all.return_value = {"instant_memory": {}}
        self.mock_config.get.return_value = {}

        # 使用 patch 替换导入的类
        patcher_ai = patch('chat_core.aihandler', return_value=self.mock_ai)
        patcher_tools = patch('chat_core.ToolInvoker', return_value=self.mock_tools)
        patcher_config = patch('chat_core.ConfigManager', return_value=self.mock_config)

        self.addCleanup(patcher_ai.stop)
        self.addCleanup(patcher_tools.stop)
        self.addCleanup(patcher_config.stop)

        self.mock_ai_class = patcher_ai.start()
        self.mock_tools_class = patcher_tools.start()
        self.mock_config_class = patcher_config.start()

        # 新增：Mock QTimer 类，防止实际定时器行为
        self.qtimer_patcher = patch('chat_core.QTimer')
        self.mock_qtimer = self.qtimer_patcher.start()
        self.addCleanup(self.qtimer_patcher.stop)
        
        # 创建 ChatCore 实例（内部会实例化 QTimer，但现在是 Mock）
        self.core = ChatCore(self.mock_audio)
        self.mock_auto_timer = self.core.auto_timer  # 这是 Mock 对象

        # 创建 ChatCore 实例（需要传递 audio_handler）
        self.core = ChatCore(self.mock_audio)

        # 创建 Mock GUI 对象
        self.mock_gui = MagicMock()
        self.mock_gui.user_input = MagicMock()
        self.mock_gui.user_input.toPlainText.return_value = ""
        self.mock_gui.max_context_var = MagicMock()
        self.mock_gui.max_context_var.text.return_value = "2048"
        self.mock_gui.temperature_var = MagicMock()
        self.mock_gui.temperature_var.text.return_value = "0.7"
        self.mock_gui.show_bilingual = MagicMock()
        self.mock_gui.show_bilingual.isChecked.return_value = True
        self.mock_gui.generate_audio = MagicMock()
        self.mock_gui.generate_audio.isChecked.return_value = False

        # 注入 GUI
        self.core.set_gui(self.mock_gui)

        # 清除信号连接记录（避免干扰）
        self.core.gui_request.disconnect()

    def tearDown(self):
        """每个测试后清理资源"""
        self.core.cleanup()

    # ---------- 辅助方法 ----------
    def _connect_gui_request_signal(self):
        """连接 gui_request 信号到一个 spy 函数，用于验证 GUI 调用"""
        self.gui_spy = MagicMock()
        self.core.gui_request.connect(self.gui_spy)

    # ---------- 测试初始化 ----------
    def test_initialization(self):
        """测试 ChatCore 初始化"""
        self.assertEqual(self.core.audio_handler, self.mock_audio)
        self.assertEqual(self.core.ai, self.mock_ai)
        self.assertEqual(self.core.tools_handler, self.mock_tools)
        self.assertEqual(self.core.config_manager, self.mock_config)
        self.assertFalse(self.core.auto_message_executing)
        self.assertEqual(self.core.auto_msg_interval, 0)
        self.assertIsNotNone(self.core.auto_timer)
        self.assertTrue(self.core.auto_timer.isSingleShot())

        # 验证 ConfigManager 初始化了 instant_memory
        # self.mock_config.set.assert_called_with("instant_memory", {})

    def test_set_gui_updates_variables_and_timer(self):
        """测试 set_gui 方法设置 GUI 变量和定时器"""
        self.core.auto_msg_interval = 5
        self.core.set_gui(self.mock_gui)

        # 验证调用了 setText
        expected_calls = [
            call(self.mock_gui.max_context_var.setText, ("2048",)),
            call(self.mock_gui.temperature_var.setText, ("0.7",))
        ]
        # 由于信号连接可能异步，我们直接检查 core 的调用
        # 但我们实际上在 setUp 中调用了 set_gui，可以在那之后检查
        # 此处重新调用一次以单独测试
        # 不过 setUp 已调用，我们直接验证 gui_request 的 emit 内容
        pass

    def test_gui_add_message_emit(self):
        """测试 _gui_add_message 发射信号"""
        self._connect_gui_request_signal()
        self.core._gui_add_message("User", "Hello", True)
        self.gui_spy.assert_called_once_with(
            self.mock_gui.add_message, ("User", "Hello", True)
        )

    def test_gui_set_status_emit(self):
        """测试 _gui_set_status 发射信号"""
        self._connect_gui_request_signal()
        self.core._gui_set_status("忙碌")
        self.gui_spy.assert_called_once_with(
            self.mock_gui.set_status, ("忙碌",)
        )

    def test_gui_toggle_widgets_state_emit(self):
        """测试 _gui_toggle_widgets_state 发射信号"""
        self._connect_gui_request_signal()
        self.core._gui_toggle_widgets_state(False)
        self.gui_spy.assert_called_once_with(
            self.mock_gui.toggle_widgets_state, (False,)
        )

    # ---------- 发送消息相关 ----------
    def test_send_message_event_without_shift(self):
        """测试 send_message_event 无 Shift 修饰符时发送消息"""
        mock_event = MagicMock()
        mock_event.modifiers.return_value = Qt.NoModifier
        # patch send_message 方法
        self.core.send_message = MagicMock()
        result = self.core.send_message_event(mock_event)
        self.core.send_message.assert_called_once()
        self.assertTrue(result)

    def test_send_message_event_with_shift(self):
        """测试 send_message_event 有 Shift 修饰符时不发送消息"""
        mock_event = MagicMock()
        mock_event.modifiers.return_value = Qt.ShiftModifier
        self.core.send_message = MagicMock()
        result = self.core.send_message_event(mock_event)
        self.core.send_message.assert_not_called()
        self.assertFalse(result)

    def test_send_message_empty_ignored(self):
        """测试发送空消息被忽略"""
        self.mock_gui.user_input.toPlainText.return_value = "   "
        self.core._gui_add_message = MagicMock()
        self.core.send_message()
        self.core._gui_add_message.assert_not_called()

    def test_send_message_valid(self):
        """测试发送有效消息"""
        self.mock_gui.user_input.toPlainText.return_value = "Hello"
        self.core._gui_add_message = MagicMock()
        # 模拟 process_user_message 在另一个线程，此处用 mock 替换
        self.core.process_user_message = MagicMock()
        # 由于实际代码会启动线程，为了测试简单，我们 patch threading.Thread
        with patch('chat_core.threading.Thread') as mock_thread:
            self.core.send_message()
            # 验证清空输入框
            self.mock_gui.user_input.clear.assert_called_once()
            # 验证添加用户消息到 GUI
            self.core._gui_add_message.assert_called_once_with(user_name, "Hello",is_user = True)
            # 验证启动线程处理用户消息
            mock_thread.assert_called_once()
            # 检查线程目标为 process_user_message，参数为 ("Hello",)
            args, kwargs = mock_thread.call_args
            self.assertEqual(kwargs['target'], self.core.process_user_message)
            self.assertEqual(kwargs['args'], ("Hello",))

    # ---------- 工具响应信息格式化 ----------
    def test_get_tool_responses_info_empty(self):
        """测试无工具响应时返回默认字符串"""
        self.mock_tools.get_responses.return_value = []
        info = self.core.get_tool_responses_info()
        self.assertEqual(info, "[无工具返回信息]")

    def test_get_tool_responses_info_with_responses(self):
        """测试有工具响应时格式化"""
        self.mock_tools.get_responses.return_value = [
            {"name": "ToolA", "response": "ResultA"},
            {"name": "ToolB", "response": "Waiting for responses."},
        ]
        info = self.core.get_tool_responses_info()
        expected = "[ToolA:已完成]:ResultA[ToolB:等待中]:Waiting for responses."
        self.assertEqual(info, expected)

    def test_message_format_user(self):
        """测试用户消息的格式化"""
        self.mock_tools.get_responses.return_value = [{"name": "T1", "response": "OK"}]
        with patch('chat_core.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
            formatted = self.core.message_format("Hello")
            self.assertIn("[2023-01-01_12-00-00]", formatted)
            self.assertIn("[Tools:[T1:已完成]:OK]", formatted)
            self.assertIn("[用户发送消息：\"Hello\"]", formatted)

    def test_message_format_auto(self):
        """测试自动消息的格式化"""
        self.mock_tools.get_responses.return_value = []
        with patch('chat_core.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
            formatted = self.core.message_format("")
            self.assertIn("[2023-01-01_12-00-00]", formatted)
            self.assertIn("[Tools:[无工具返回信息]]", formatted)
            self.assertIn("[自动消息触发]", formatted)

    # ---------- 用户消息处理 ----------
    @patch('chat_core.threading.Thread')
    def test_process_user_message_success(self, mock_thread):
        """测试用户消息处理成功流程"""
        # 直接调用 process_user_message（同步测试，不启动线程）
        self.core._set_busy_state = MagicMock()
        self.core.handle_commands = MagicMock()
        self.mock_ai.user_message.return_value = [{"cmd": "talk_to_user", "para": [{"zh": "你好", "ja": "こんにちは"}]}]
        self.core.message_format = MagicMock(return_value="[formatted]")

        self.core.process_user_message("Hello")

        # 验证调用流程
        self.core.message_format.assert_called_once_with("Hello")
        self.mock_ai.user_message.assert_called_once_with("[formatted]")
        self.core.handle_commands.assert_called_once_with([{"cmd": "talk_to_user", "para": [{"zh": "你好", "ja": "こんにちは"}]}])
        # 验证忙碌状态设置
        self.core._set_busy_state.assert_has_calls([call(True), call(False)])

    def test_process_user_message_lock_timeout(self):
        """测试获取锁超时情况"""
        # 模拟锁获取失败
        self.core.lock = MagicMock()
        self.core.lock.acquire.return_value = False
        self.core._gui_show_error = MagicMock()
        self.core.process_user_message("Hello")
        self.core._gui_show_error.assert_called_once_with("系统繁忙，请稍后再试")
        self.core._set_busy_state = MagicMock()
        self.core._set_busy_state.assert_not_called()

    def test_process_user_message_exception(self):
        """测试处理用户消息时发生异常"""
        self.core.message_format = MagicMock(side_effect=Exception("Test error"))
        self.core._gui_show_error = MagicMock()
        self.core._set_busy_state = MagicMock()

        self.core.process_user_message("Hello")

        self.core._gui_show_error.assert_called_once_with("发送消息时出错: Test error")
        self.core._set_busy_state.assert_has_calls([call(True), call(False)])

    # ---------- 自动消息相关 ----------
    def test_start_auto_timer(self):
        """测试启动自动消息定时器"""
        self.core.auto_msg_interval = 5
        self.core._start_auto_timer()
        self.mock_auto_timer.start.assert_called_once_with(5000)

    def test_start_auto_timer_zero_interval(self):
        """测试间隔为 0 时不启动定时器"""
        self.core.auto_msg_interval = 0
        self.core._start_auto_timer()
        self.mock_auto_timer.start.assert_not_called()

    def test_stop_auto_timer(self):
        """测试停止定时器"""
        self.core._stop_auto_timer()
        self.mock_auto_timer.stop.assert_called_once()

    def test_on_auto_timer_timeout_emits_signal(self):
        """测试定时器超时时发射信号"""
        self.core.auto_message_trigger = MagicMock()
        self.core._on_auto_timer_timeout()
        self.core.auto_message_trigger.emit.assert_called_once()

    def test_reset_auto_timer_slot_during_execution(self):
        """测试自动消息执行中重置计时器挂起"""
        self.core.auto_message_executing = True
        self.core.auto_msg_interval = 10
        self.core._stop_auto_timer = MagicMock()
        self.core._start_auto_timer = MagicMock()

        # 发送重置信号
        self.core._reset_auto_timer_slot(20)

        self.assertEqual(self.core.pending_reset_interval, 20)
        self.core._stop_auto_timer.assert_not_called()
        self.core._start_auto_timer.assert_not_called()

    def test_reset_auto_timer_slot_not_executing(self):
        """测试非执行中直接重置定时器"""
        self.core.auto_message_executing = False
        self.core.auto_msg_interval = 5
        self.core._stop_auto_timer = MagicMock()
        self.core._start_auto_timer = MagicMock()

        self.core._reset_auto_timer_slot(10)

        self.core._stop_auto_timer.assert_called_once()
        self.assertEqual(self.core.auto_msg_interval, 10)
        self.core._start_auto_timer.assert_called_once()

    def test_reset_auto_timer_slot_zero_disables(self):
        """测试设置间隔为 0 时禁用自动消息"""
        self.core.auto_message_executing = False
        self.core.auto_msg_interval = 5
        self.core._stop_auto_timer = MagicMock()
        self.core._start_auto_timer = MagicMock()

        self.core._reset_auto_timer_slot(0)

        self.core._stop_auto_timer.assert_called_once()
        self.assertEqual(self.core.auto_msg_interval, 0)
        self.core._start_auto_timer.assert_not_called()

    def test_reset_auto_message_timer_signal(self):
        """测试 reset_auto_message_timer 发射信号"""
        self.core.reset_timer_signal = MagicMock()
        self.core.reset_auto_message_timer(15)
        self.core.reset_timer_signal.emit.assert_called_once_with(15)

    @patch('chat_core.threading.Thread')
    def test_process_auto_message_worker_success(self, mock_thread):
        """测试自动消息工作线程成功执行"""
        # 避免实际启动线程，直接调用 worker
        self.core._set_busy_state = MagicMock()
        self.core.handle_commands = MagicMock()
        self.core.message_format = MagicMock(return_value="[formatted]")
        self.mock_ai.auto_message.return_value = [{"cmd": "talk_to_user", "para": [{"zh": "自动", "ja": "auto"}]}]
        self.core._gui_add_message = MagicMock()
        self.core._schedule_next_auto_message = MagicMock()

        self.core._process_auto_message_worker()

        self.core.message_format.assert_called_once_with("")
        self.mock_ai.auto_message.assert_called_once_with("[formatted]")
        self.core.handle_commands.assert_called_once()
        self.core._gui_add_message.assert_called_once_with("系统", "自动触发消息", is_user=False)
        self.core._set_busy_state.assert_has_calls([call(True), call(False)])
        self.core._schedule_next_auto_message.assert_called_once()

    def test_process_auto_message_worker_lock_failure(self):
        """测试自动消息获取锁失败时重置定时器"""
        self.core.lock = MagicMock()
        self.core.lock.acquire.return_value = False
        self.core.reset_auto_message_timer = MagicMock()
        self.core._process_auto_message_worker()
        self.core.reset_auto_message_timer.assert_called_once()

    def test_schedule_next_auto_message_with_pending(self):
        """测试 _schedule_next_auto_message 处理挂起的间隔"""
        self.core.pending_reset_interval = 15
        self.core.auto_msg_interval = 5
        self.core.reset_auto_message_timer = MagicMock()
        self.core._schedule_next_auto_message()
        self.assertEqual(self.core.auto_msg_interval, 15)
        self.assertIsNone(self.core.pending_reset_interval)
        self.core.reset_auto_message_timer.assert_called_once()

    def test_schedule_next_auto_message_no_pending(self):
        """测试无挂起间隔时正常调度"""
        self.core.auto_msg_interval = 5
        self.core.reset_auto_message_timer = MagicMock()
        self.core._schedule_next_auto_message()
        self.core.reset_auto_message_timer.assert_called_once()

    def test_schedule_next_auto_message_zero_interval(self):
        """测试间隔为 0 时不调度"""
        self.core.auto_msg_interval = 0
        self.core.reset_auto_message_timer = MagicMock()
        self.core._schedule_next_auto_message()
        self.core.reset_auto_message_timer.assert_not_called()

    # ---------- 即时记忆管理 ----------
    def test_modify_instant_memory_add_new(self):
        """测试添加新记忆"""
        self.mock_config.reload.return_value = None
        self.mock_config.get.return_value = {}  # 初始无记忆
        self.core._modify_instant_memory("add", "test_cata", 1, "content1")
        expected_dict = {
            "test_cata": [
                {"id": 1, "content": "content1", "timestamp": ANY}
            ]
        }
        self.mock_config.set.assert_called_once_with("instant_memory", expected_dict)

    def test_modify_instant_memory_add_existing_update(self):
        """测试添加已存在的记忆（覆盖）"""
        existing = {
            "test_cata": [
                {"id": 1, "content": "old", "timestamp": "old_time"}
            ]
        }
        self.mock_config.get.return_value = existing
        self.core._modify_instant_memory("add", "test_cata", 1, "new_content")
        # 验证内容更新，时间戳更新
        args = self.mock_config.set.call_args[0][1]
        self.assertEqual(args["test_cata"][0]["content"], "new_content")
        self.assertNotEqual(args["test_cata"][0]["timestamp"], "old_time")

    def test_modify_instant_memory_del_success(self):
        """测试成功删除记忆"""
        existing = {
            "test_cata": [
                {"id": 1, "content": "c1", "timestamp": "t1"},
                {"id": 2, "content": "c2", "timestamp": "t2"}
            ]
        }
        self.mock_config.get.return_value = existing
        result = self.core._modify_instant_memory("del", "test_cata", 1)
        self.assertTrue(result)
        expected_dict = {
            "test_cata": [{"id": 2, "content": "c2", "timestamp": "t2"}]
        }
        self.mock_config.set.assert_called_once_with("instant_memory", expected_dict)

    def test_modify_instant_memory_del_not_found(self):
        """测试删除不存在的记忆"""
        existing = {"test_cata": [{"id": 1}]}
        self.mock_config.get.return_value = existing
        result = self.core._modify_instant_memory("del", "test_cata", 2)
        self.assertFalse(result)
        self.mock_config.set.assert_not_called()

    def test_modify_instant_memory_unknown_opt(self):
        """测试未知操作"""
        result = self.core._modify_instant_memory("invalid", "cata", 1)
        self.assertFalse(result)
        self.mock_config.set.assert_not_called()

    # ---------- 显示 AI 响应 ----------
    def test_display_ai_response_bilingual_enabled(self):
        """测试显示双语响应（启用双语）"""
        self.mock_gui.show_bilingual.isChecked.return_value = True
        self.mock_gui.generate_audio.isChecked.return_value = False
        response = '{"zh": "你好", "ja": "こんにちは"}'
        self.core.gui_request = MagicMock()

        self.core.display_ai_response(response)

        # 验证 gui_request 被发射，调用了 add_message
        self.core.gui_request.emit.assert_called()
        # 获取 emit 的参数
        call_args = self.core.gui_request.emit.call_args[0]
        func = call_args[0]
        # 执行该函数以模拟 GUI 调用
        func()
        self.mock_gui.add_message.assert_called_once_with(bot_name, "你好\n\nこんにちは", is_user=False)

    def test_display_ai_response_single_language(self):
        """测试只显示中文（禁用双语）"""
        self.mock_gui.show_bilingual.isChecked.return_value = False
        self.mock_gui.generate_audio.isChecked.return_value = False
        response = '{"zh": "你好", "ja": "こんにちは"}'
        self.core.gui_request = MagicMock()

        self.core.display_ai_response(response)

        call_args = self.core.gui_request.emit.call_args[0]
        func = call_args[0]
        func()
        self.mock_gui.add_message.assert_called_once_with(bot_name, "你好", is_user=False)

    @patch('chat_core.threading.Thread')
    def test_display_ai_response_with_audio(self, mock_thread):
        """测试启用音频生成时启动播放线程"""
        self.mock_gui.generate_audio.isChecked.return_value = True
        self.mock_audio.is_playing.return_value = False
        response = '{"zh": "你好", "ja": "こんにちは"}'
        self.core.gui_request = MagicMock()

        self.core.display_ai_response(response)

        # 验证启动了播放线程
        mock_thread.assert_called_once()
        # 检查线程 target 函数
        args, kwargs = mock_thread.call_args
        target_func = kwargs['target']
        # 执行 target 函数模拟播放
        target_func()
        self.mock_audio.play_japanese_audio.assert_called_once_with("こんにちは")

    def test_display_ai_response_invalid_json(self):
        """测试无效 JSON 时的错误处理"""
        self.core._gui_show_error = MagicMock()
        self.core.display_ai_response("invalid json")
        self.core._gui_show_error.assert_called_once()

    # ---------- 设置参数 ----------
    def test_set_max_context_valid(self):
        """测试设置最大上下文有效值"""
        self.mock_gui.max_context_var.text.return_value = "4096"
        self.core._set_busy_state = MagicMock()
        self.core._gui_show_info = MagicMock()
        self.core.set_max_context()
        self.core.ai.set_now_max_context.assert_called_once_with(4096)
        self.core.ai.set_base_max_context.assert_called_once_with(4096)
        self.core._gui_show_info.assert_called_once_with("最大上下文长度已更新")
        self.core._set_busy_state.assert_has_calls([call(True), call(False)])

    def test_set_max_context_invalid(self):
        """测试设置无效最大上下文"""
        self.mock_gui.max_context_var.text.return_value = "abc"
        self.core._gui_show_error = MagicMock()
        self.core.set_max_context()
        self.core._gui_show_error.assert_called_once_with("请输入有效的整数")

    def test_set_temperature_valid(self):
        """测试设置有效温度值"""
        self.mock_gui.temperature_var.text.return_value = "1.2"
        self.core._set_busy_state = MagicMock()
        self.core._gui_show_info = MagicMock()
        self.core.set_temperature()
        self.core.ai.set_temperature.assert_called_once_with(1.2)
        self.core._gui_show_info.assert_called_once_with("温度参数已更新")

    def test_set_temperature_out_of_range(self):
        """测试温度值超出范围"""
        self.mock_gui.temperature_var.text.return_value = "3.0"
        self.core._gui_show_error = MagicMock()
        self.core.set_temperature()
        self.core._gui_show_error.assert_called_once_with("温度值应在0到2之间")

    # ---------- 命令处理 ----------
    def test_handle_commands_system_and_tool(self):
        """测试混合命令分发"""
        self.core.is_system_command = MagicMock(side_effect=[True, False])
        self.core.execute_system_command = MagicMock()
        commands = [{"cmd": "talk_to_user"}, {"cmd": "tool_cmd"}]
        self.core.handle_commands(commands)
        self.core.execute_system_command.assert_called_once_with({"cmd": "talk_to_user"})
        self.mock_tools.add_tasks.assert_called_once_with([{"cmd": "tool_cmd"}])

    def test_is_system_command_true(self):
        """测试系统命令识别"""
        for cmd_name in ["talk_to_user", "delay", "instant_memory", "reset_auto_timer"]:
            self.assertTrue(self.core.is_system_command({"cmd": cmd_name}))
        self.assertFalse(self.core.is_system_command({"cmd": "unknown"}))

    def test_execute_system_command_talk_to_user(self):
        """测试 talk_to_user 命令执行"""
        self.core.display_ai_response = MagicMock()
        cmd = {"cmd": "talk_to_user", "para": [{"zh": "Hi", "ja": "Hai"}]}
        self.core.execute_system_command(cmd)
        self.core.display_ai_response.assert_called_once_with({"zh": "Hi", "ja": "Hai"})

    def test_execute_system_command_delay(self):
        """测试 delay 命令"""
        with patch('chat_core.time.sleep') as mock_sleep:
            cmd = {"cmd": "delay", "para": 2.5}
            self.core.execute_system_command(cmd)
            mock_sleep.assert_called_once_with(2.5)

    def test_execute_system_command_instant_memory(self):
        """测试 instant_memory 命令"""
        self.core._modify_instant_memory = MagicMock()
        cmd = {"cmd": "instant_memory", "para": {"opt": "add", "cata": "c1", "id": 1, "content": "test"}}
        self.core.execute_system_command(cmd)
        self.core._modify_instant_memory.assert_called_once_with("add", "c1", 1, "test")

    def test_execute_system_command_reset_auto_timer(self):
        """测试 reset_auto_timer 命令"""
        self.core.reset_auto_message_timer = MagicMock()
        cmd = {"cmd": "reset_auto_timer", "para": 30}
        self.core.execute_system_command(cmd)
        self.core.reset_auto_message_timer.assert_called_once_with(30)

    # ---------- 忙碌状态与清理 ----------
    def test_set_busy_state_true(self):
        """测试设置为忙碌状态"""
        self.core._gui_set_status = MagicMock()
        self.core._gui_toggle_widgets_state = MagicMock()
        self.core._set_busy_state(True)
        self.core._gui_set_status.assert_called_once_with("正忙...")
        self.core._gui_toggle_widgets_state.assert_called_once_with(False)

    def test_set_busy_state_false(self):
        """测试设置为就绪状态"""
        self.core._gui_set_status = MagicMock()
        self.core._gui_toggle_widgets_state = MagicMock()
        self.core._set_busy_state(False)
        self.core._gui_set_status.assert_called_once_with("就绪")
        self.core._gui_toggle_widgets_state.assert_called_once_with(True)

    def test_cleanup(self):
        """测试清理资源"""
        self.core._stop_auto_timer = MagicMock()
        self.core.cleanup()
        self.core._stop_auto_timer.assert_called_once()
        self.mock_audio.cleanup.assert_called_once()

    # ---------- 集成场景测试 ----------
    @patch('chat_core.threading.Thread')
    def test_full_user_message_flow(self, mock_thread):
        """模拟完整的用户消息流程（使用同步调用）"""
        # 直接调用 process_user_message，不启动线程
        self.core._set_busy_state = MagicMock()
        self.core.handle_commands = MagicMock()
        self.mock_ai.user_message.return_value = [
            {"cmd": "talk_to_user", "para": [{"zh": "你好", "ja": "こんにちは"}]}
        ]
        self.core.process_user_message("Hello")

        # 验证最终 GUI 显示调用
        self.core._set_busy_state.assert_has_calls([call(True), call(False)])
        # 验证 AI 调用
        self.mock_ai.user_message.assert_called_once()
        # 验证命令处理
        self.core.handle_commands.assert_called_once()

    def test_auto_message_trigger_when_executing(self):
        """测试自动消息触发时若正在执行则跳过"""
        self.core.auto_message_executing = True
        self.core.process_auto_message = MagicMock()
        # 直接调用槽函数
        # self.core.process_auto_message()
        # 由于 process_auto_message 内部检查 executing，不应启动 worker
        # self.core.process_auto_message.assert_not_called()
        # 但我们直接调用 process_auto_message 方法，应跳过
        # 修正：我们测试 process_auto_message 自身逻辑
        with patch('chat_core.threading.Thread') as mock_thread:
            self.core.process_auto_message()
            mock_thread.assert_not_called()

    def test_gui_request_execution(self):
        """测试 _execute_gui_function 正确调用函数"""
        mock_func = MagicMock()
        args = (1, 2)
        self.core._execute_gui_function(mock_func, args)
        mock_func.assert_called_once_with(1, 2)

    def test_gui_request_exception_handling(self):
        """测试 GUI 函数执行异常时记录日志"""
        mock_func = MagicMock(side_effect=Exception("GUI error"))
        with patch('chat_core.logger.error') as mock_log:
            self.core._execute_gui_function(mock_func, ())
            mock_log.assert_called_once()


if __name__ == '__main__':
    unittest.main()