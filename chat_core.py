from enum import auto
from multiprocessing import process
import threading
import time
import datetime
import json
from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal
from AIHandler import aihandler
from datetime import datetime
from ToolsHandler import ToolInvoker
import logger
from typing import List, Dict

user_name = "User"
bot_name = "ChatBot"

class ChatCore(QObject):
    # 定义信号
    auto_message_trigger = pyqtSignal()          # 触发自动消息
    reset_timer_signal = pyqtSignal(int)         # 请求重置计时器（参数为新间隔，-1表示只重置不修改间隔）

    def __init__(self, audio_handler):
        super().__init__()
        self.gui = None
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.Lock()
        self.auto_msg_interval = 0          
        self.auto_message_executing = False       # 防止自动消息重复执行
        self.pending_reset_interval = None        # 待重置的间隔（若自动消息执行中）

        # 创建单次定时器（主线程使用）
        self.auto_timer = QTimer()
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._on_auto_timer_timeout)

        self.tools_handler = ToolInvoker()
        logger.logger.info("ChatCore初始化完成")

        # 连接内部信号
        self.auto_message_trigger.connect(self.process_auto_message)
        self.reset_timer_signal.connect(self._reset_auto_timer_slot)

    def set_gui(self, gui):
        self.gui = gui
        self.gui.max_context_var.setText(str(self.ai.get_now_max_context()))
        self.gui.temperature_var.setText(str(self.ai.get_temperature()))
        logger.logger.info("GUI注入完成")
        # 启动自动消息计时（仅当间隔大于0时）
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.info("自动消息间隔为0，已禁用自动消息")
        logger.logger.info("自动消息定时器初始化完成")

    def send_message_event(self, event):
        if not event.modifiers() & Qt.ShiftModifier:
            self.send_message()
            return True
        return False

    def send_message(self):
        message = self.gui.user_input.toPlainText().strip()
        if not message:
            return
        self.gui.user_input.clear()
        self.gui.add_message(user_name, message, is_user=True)
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()

    def get_tool_responses_info(self):
        tool_responses = self.tools_handler.get_responses()
        if not tool_responses:
            return "[无工具返回信息]"
        response_parts = []
        for resp in tool_responses:
            status = "已完成" if resp['response'] != "Waiting for responses." else "等待中"
            response_parts.append(f"[{resp['name']}:{status}]:{resp['response']}")
        return "".join(response_parts)

    def message_format(self, message):
        tool_info = self.get_tool_responses_info()
        time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if message:
            return f"[{time_str}][Tools:{tool_info}][用户发送消息：\"{message}\"]"
        return f"[{time_str}][Tools:{tool_info}][自动消息触发]"

    def process_user_message(self, message):
        logger.logger.info(f"处理用户消息请求：{message}")
        self.set_busy_state(True)
        try:
            formatted_message = self.message_format(message)
            commands = self.ai.user_message(formatted_message)
            self.handle_commands(commands)
        except Exception as e:
            self.gui.show_error(f"发送消息时出错: {str(e)}")
            logger.logger.error(f"发送消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.debug(f"处理用户消息完成")

    # ---------- 自动消息定时器相关方法 ----------
    def _start_auto_timer(self):
        """启动定时器（停止当前，重新开始倒计时）"""
        self.auto_timer.stop()
        if self.auto_msg_interval > 0:
            self.auto_timer.start(self.auto_msg_interval * 1000)  # 转换为毫秒
            logger.logger.debug(f"自动消息定时器启动，间隔 {self.auto_msg_interval} 秒")
        else:
            logger.logger.debug("自动消息间隔为0，定时器未启动")

    def _stop_auto_timer(self):
        """停止定时器"""
        self.auto_timer.stop()
        logger.logger.debug("自动消息定时器已停止")

    def _on_auto_timer_timeout(self):
        """定时器超时，触发自动消息信号"""
        logger.logger.debug("自动消息定时器超时，触发自动消息")
        self.auto_message_trigger.emit()

    def _schedule_next_auto_message(self):
        """自动消息执行完成后，调度下一次自动消息（处理 pending 重置）"""
        # 如果有待重置的间隔，先应用
        if self.pending_reset_interval is not None:
            new_interval = self.pending_reset_interval
            self.pending_reset_interval = None
            # 新间隔可以是0（禁用）或正数
            if new_interval is not None and new_interval >= 0:
                self.auto_msg_interval = new_interval
                if new_interval == 0:
                    logger.logger.info("自动消息已禁用（间隔设为0）")
                else:
                    logger.logger.info(f"应用待重置的自动消息间隔：{self.auto_msg_interval} 秒")
            else:
                logger.logger.warning("待重置的间隔无效（负数），忽略")
        # 启动下一次计时（仅当间隔>0）
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.debug("自动消息间隔为0，不再调度下一次自动消息")

    def _reset_auto_timer_slot(self, new_interval: int):
        """【主线程槽函数】实际执行重置计时器逻辑"""
        # 如果自动消息正在执行，则延迟重置
        if self.auto_message_executing:
            # 允许 new_interval 为 0（禁用）或正数，负数视为无效（不改变）
            if new_interval is not None and new_interval >= 0:
                self.pending_reset_interval = new_interval
                logger.logger.info(f"自动消息执行中，重置计时器请求已挂起（新间隔：{new_interval}秒）")
            else:
                logger.logger.warning(f"无效的待重置间隔：{new_interval}，已忽略")
            return

        # 否则立即重置
        self._stop_auto_timer()
        if new_interval is not None and new_interval >= 0:
            self.auto_msg_interval = new_interval
            if new_interval == 0:
                logger.logger.info("自动消息已禁用（间隔设为0）")
            else:
                logger.logger.info(f"自动消息间隔已更新为 {self.auto_msg_interval} 秒")
        elif new_interval is not None and new_interval < 0:
            logger.logger.warning(f"无效的自动消息间隔：{new_interval}，保持原间隔")
        # 重新开始计时（仅当间隔>0）
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.debug("自动消息间隔为0，定时器已停止且不再启动")

    def reset_auto_message_timer(self, new_interval: int = None):
        """
        重置自动消息计时器（线程安全，通过信号转到主线程）
        :param new_interval: 新的自动消息间隔（秒），设为0可禁用自动消息。
                             若为 None 则只重置计时不改变间隔（即重新开始倒计时）。
        """
        # 如果 new_interval 为 None，传递 -1 表示只重置计时（不改变间隔）
        interval = new_interval if new_interval is not None else -1
        self.reset_timer_signal.emit(interval)

    # ---------- 自动消息处理 ----------
    def process_auto_message(self):
        """自动消息执行逻辑（在主线程中执行）"""
        if self.auto_message_executing:
            logger.logger.info("自动消息正在执行，跳过本次触发")
            return

        logger.logger.debug("执行自动消息")
        self.auto_message_executing = True
        self.set_busy_state(True)

        try:
            formatted_message = self.message_format("")
            commands = self.ai.auto_message(formatted_message)
            self.handle_commands(commands)
            self.gui.add_message("系统", "自动触发消息", is_user=False)
        except Exception as e:
            self.gui.show_error(f"自动消息时出错: {str(e)}")
            logger.logger.error(f"自动消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            self.auto_message_executing = False
            # 执行完成后调度下一次自动消息（处理 pending 重置）
            self._schedule_next_auto_message()
            logger.logger.info("自动消息处理完成")

    # ---------- 其他原有方法 ----------
    def display_ai_response(self, response):
        try:
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response

            zh_text = response_data.get("zh", "")
            ja_text = response_data.get("ja", "")
            display_text = zh_text

            if self.gui.show_bilingual.isChecked() and ja_text:
                display_text = f"{zh_text}\n\n{ja_text}"

            self.gui.add_message(bot_name, display_text, is_user=False)

            if self.gui.generate_audio.isChecked() and ja_text:
                def play_audio():
                    while self.audio_handler.is_playing():
                        time.sleep(0.2)
                    self.audio_handler.play_japanese_audio(ja_text)
                threading.Thread(target=play_audio, daemon=True).start()

            logger.logger.debug(f"成功显示消息：{display_text}")

        except Exception as e:
            self.gui.show_error(f"显示消息时出错: {str(e)}")
            logger.logger.error(f"显示消息时出错: {str(e)}")

    def set_max_context(self):
        try:
            max_context = int(self.gui.max_context_var.text())
            self.set_busy_state(True)
            self.ai.set_now_max_context(max_context)
            self.ai.set_base_max_context(max_context)
            self.gui.show_info("最大上下文长度已更新")
            logger.logger.info(f"最大上下文长度已更新：{max_context}")
        except ValueError:
            self.gui.show_error("请输入有效的整数")
            logger.logger.error("用户输入的最大上下文长度不是有效的整数")
        except Exception as e:
            self.gui.show_error(f"设置最大上下文时出错: {str(e)}")
        finally:
            self.set_busy_state(False)

    def set_temperature(self):
        try:
            temperature = float(self.gui.temperature_var.text())
            if not 0 <= temperature <= 2:
                raise ValueError("温度值应在0到2之间")
            self.set_busy_state(True)
            self.ai.set_temperature(temperature)
            self.gui.show_info("温度参数已更新")
            logger.logger.info(f"温度已更新：{temperature}")
        except ValueError as e:
            self.gui.show_error(str(e))
        except Exception as e:
            self.gui.show_error(f"设置温度参数时出错: {str(e)}")
        finally:
            self.set_busy_state(False)

    def handle_commands(self, commands: List[Dict]) -> None:
        logger.logger.debug(f"开始处理来自AI请求的命令：{commands}")
        for cmd in commands:
            if self.is_system_command(cmd):
                self.execute_system_command(cmd)
            else:
                self.tools_handler.add_tasks([cmd])
        logger.logger.info(f"来自AI请求的命令已处理完成")

    def is_system_command(self, cmd: Dict) -> bool:
        system_commands = {"talk_to_user", "delay", "instant_memory", "reset_auto_timer"}
        return cmd.get("cmd") in system_commands

    def execute_system_command(self, cmd: Dict):
        try:
            cmd_name = cmd["cmd"]
            if cmd_name == "talk_to_user":
                if isinstance(cmd["para"], list):
                    for item in cmd["para"]:
                        if isinstance(item, dict) and "zh" in item and "ja" in item:
                            self.display_ai_response(item)
            elif cmd_name == "delay":
                time.sleep(cmd["para"])
            elif cmd_name == "instant_memory":
                self.ai.set_instant_memory(cmd["para"])
            elif cmd_name == "reset_auto_timer":
                new_interval = cmd.get("para")
                # 允许 AI 传入 0 来禁用自动消息
                if isinstance(new_interval, int):
                    self.reset_auto_message_timer(new_interval)
                else:
                    logger.logger.warning(f"reset_auto_timer 参数类型错误：{new_interval}")
        except Exception as e:
            logger.logger.error(f"系统命令执行失败：{str(e)}")

    def set_busy_state(self, busy):
        try:
            if busy:
                self.lock.acquire(timeout=1)
                self.gui.set_status("正忙...")
                self.gui.toggle_widgets_state(False)
            else:
                self.gui.set_status("就绪")
                self.gui.toggle_widgets_state(True)
                if self.lock.locked():
                    self.lock.release()
        except:
            pass

    def cleanup(self):
        """安全退出，停止所有定时器"""
        self._stop_auto_timer()
        if self.audio_handler:
            self.audio_handler.cleanup()
        logger.logger.info("ChatCore安全退出完成")