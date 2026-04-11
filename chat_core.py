import threading
import time
import json
from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal
from AIHandler import aihandler
from datetime import datetime  # 修复：保留一个 datetime 导入
from ToolsHandler import ToolInvoker
import logger
from typing import List, Dict

# 新增导入
from config_manager import ConfigManager

user_name = "User"
bot_name = "ChatBot"

class ChatCore(QObject):
    # 定义信号
    auto_message_trigger = pyqtSignal()          # 触发自动消息
    reset_timer_signal = pyqtSignal(int)         # 请求重置计时器（参数为新间隔，-1表示只重置不修改间隔）
    gui_request = pyqtSignal(object, object)     # (function, args) 用于在主线程执行GUI操作

    def __init__(self, audio_handler):
        super().__init__()
        self.gui = None
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.RLock()              # 改为可重入锁，避免死锁
        self.auto_msg_interval = 0          
        self.auto_message_executing = False       # 防止自动消息重复执行
        self.pending_reset_interval = None        # 待重置的间隔（若自动消息执行中）

        # 创建单次定时器（主线程使用）
        self.auto_timer = QTimer()
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._on_auto_timer_timeout)

        self.tools_handler = ToolInvoker()
        logger.logger.info("ChatCore初始化完成")

        # 新增：配置管理器实例
        self.config_manager = ConfigManager()
        if "instant_memory" not in self.config_manager.get_all():
            self.config_manager.set("instant_memory", {})

        # 连接内部信号
        self.auto_message_trigger.connect(self.process_auto_message)
        self.reset_timer_signal.connect(self._reset_auto_timer_slot)
        self.gui_request.connect(self._execute_gui_function)

    def set_gui(self, gui):
        self.gui = gui
        self._gui_set_text(self.gui.max_context_var, str(self.ai.get_now_max_context()))
        self._gui_set_text(self.gui.temperature_var, str(self.ai.get_temperature()))
        logger.logger.info("GUI注入完成")
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.info("自动消息间隔为0，已禁用自动消息")

    # ---------- GUI 线程安全辅助方法 ----------
    def _execute_gui_function(self, func, args):
        """在主线程中执行指定的GUI操作"""
        try:
            func(*args)
        except Exception as e:
            logger.logger.error(f"GUI操作执行失败: {e}")

    def _gui_add_message(self, name, text, is_user):
        self.gui_request.emit(self.gui.add_message, (name, text, is_user))

    def _gui_set_status(self, text):
        self.gui_request.emit(self.gui.set_status, (text,))

    def _gui_toggle_widgets_state(self, enabled):
        self.gui_request.emit(self.gui.toggle_widgets_state, (enabled,))

    def _gui_show_error(self, text):
        self.gui_request.emit(self.gui.show_error, (text,))

    def _gui_show_info(self, text):
        self.gui_request.emit(self.gui.show_info, (text,))

    def _gui_set_text(self, widget, text):
        self.gui_request.emit(widget.setText, (text,))

    # ---------- 发送消息 ----------
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
        self._gui_add_message(user_name, message, is_user=True)
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()

    # ---------- 工具信息格式化 ----------
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

    # ---------- 用户消息处理（工作线程）----------
    def process_user_message(self, message):
        logger.logger.info(f"处理用户消息请求：{message}")
        # 获取锁，确保同一时间只有一个消息处理流程（包括自动消息）
        if not self.lock.acquire(timeout=2):
            logger.logger.error("获取锁超时，放弃处理用户消息")
            self._gui_show_error("系统繁忙，请稍后再试")
            return
        try:
            self._set_busy_state(True)
            formatted_message = self.message_format(message)
            commands = self.ai.user_message(formatted_message)
            self.handle_commands(commands)
        except Exception as e:
            self._gui_show_error(f"发送消息时出错: {str(e)}")
            logger.logger.error(f"发送消息时出错: {str(e)}")
        finally:
            self._set_busy_state(False)
            self.lock.release()
            logger.logger.debug(f"处理用户消息完成")

    # ---------- 自动消息相关 ----------
    def _start_auto_timer(self):
        """启动定时器（停止当前，重新开始倒计时）"""
        self.auto_timer.stop()
        if self.auto_msg_interval > 0:
            self.auto_timer.start(self.auto_msg_interval * 1000)
            logger.logger.debug(f"自动消息定时器启动，间隔 {self.auto_msg_interval} 秒")

    def _stop_auto_timer(self):
        self.auto_timer.stop()
        logger.logger.debug("自动消息定时器已停止")

    def _on_auto_timer_timeout(self):
        logger.logger.debug("自动消息定时器超时，触发自动消息")
        self.auto_message_trigger.emit()

    def _schedule_next_auto_message(self):
        """自动消息执行完成后，调度下一次自动消息（处理 pending 重置）"""
        if self.pending_reset_interval is not None:
            new_interval = self.pending_reset_interval
            self.pending_reset_interval = None
            if new_interval is not None and new_interval >= 0:
                self.auto_msg_interval = new_interval
                if new_interval == 0:
                    logger.logger.info("自动消息已禁用（间隔设为0）")
                else:
                    logger.logger.info(f"应用待重置的自动消息间隔：{self.auto_msg_interval} 秒")
            else:
                logger.logger.warning("待重置的间隔无效，忽略")
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.debug("自动消息间隔为0，不再调度下一次自动消息")

    def _reset_auto_timer_slot(self, new_interval: int):
        """主线程槽函数，实际执行重置计时器逻辑"""
        if self.auto_message_executing:
            if new_interval >= 0:
                self.pending_reset_interval = new_interval
                logger.logger.info(f"自动消息执行中，重置计时器请求已挂起（新间隔：{new_interval}秒）")
            else:
                # new_interval == -1 表示仅重置计时，挂起一个“无间隔改变”的请求
                self.pending_reset_interval = self.auto_msg_interval
                logger.logger.info("自动消息执行中，重置计时请求已挂起（仅重置倒计时）")
            return

        self._stop_auto_timer()
        if new_interval >= 0:
            self.auto_msg_interval = new_interval
            if new_interval == 0:
                logger.logger.info("自动消息已禁用（间隔设为0）")
            else:
                logger.logger.info(f"自动消息间隔已更新为 {self.auto_msg_interval} 秒")
        elif new_interval == -1:
            # 仅重置计时，不改变间隔
            logger.logger.debug("仅重置自动消息计时器，间隔不变")
        else:
            logger.logger.warning(f"无效的自动消息间隔：{new_interval}，保持原间隔")

        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.logger.debug("自动消息间隔为0，定时器已停止且不再启动")

    def reset_auto_message_timer(self, new_interval: int = None):
        """
        重置自动消息计时器（线程安全，通过信号转到主线程）
        :param new_interval: 新的自动消息间隔（秒），设为0可禁用。None 表示只重置计时不改变间隔。
        """
        interval = new_interval if new_interval is not None else -1
        self.reset_timer_signal.emit(interval)

    # ---------- 自动消息处理（修改：主线程仅触发，工作线程处理）----------
    def process_auto_message(self):
        """自动消息触发入口（在主线程中执行，仅负责启动线程）"""
        if self.auto_message_executing:
            logger.logger.info("自动消息正在执行，跳过本次触发")
            return
        # 将耗时逻辑放入子线程执行
        threading.Thread(target=self._process_auto_message_worker, daemon=True).start()

    def _process_auto_message_worker(self):
        """自动消息实际处理逻辑（在子线程中执行）"""
        # 获取锁，与用户消息互斥
        if not self.lock.acquire(timeout=1):
            logger.logger.warning("自动消息获取锁超时，稍后重试")
            # 重新调度定时器，稍后重试
            if self.auto_msg_interval > 0:
                self._start_auto_timer()
            return

        self.auto_message_executing = True
        try:
            self._set_busy_state(True)
            formatted_message = self.message_format("")
            commands = self.ai.auto_message(formatted_message)
            self.handle_commands(commands)
            self._gui_add_message("系统", "自动触发消息", is_user=False)
        except Exception as e:
            self._gui_show_error(f"自动消息时出错: {str(e)}")
            logger.logger.error(f"自动消息时出错: {str(e)}")
        finally:
            self._set_busy_state(False)
            self.auto_message_executing = False
            self.lock.release()
            self._schedule_next_auto_message()
            logger.logger.info("自动消息处理完成")

    # ---------- 即时记忆管理 ----------
    def _modify_instant_memory(self, opt: str, cata: str, mem_id: int, content: str = None) -> bool:
        """修改即时记忆（线程安全，锁已由上层保证）"""
        # 注意：调用此方法时，必须已经持有 self.lock
        self.config_manager.reload()
        memory_dict = self.config_manager.get("instant_memory")
        if not isinstance(memory_dict, dict):
            memory_dict = {}

        if opt == "add":
            if cata not in memory_dict:
                memory_dict[cata] = []
            category_list = memory_dict[cata]
            found = False
            for item in category_list:
                if item.get("id") == mem_id:
                    item["content"] = content
                    item["timestamp"] = datetime.now().isoformat()
                    found = True
                    break
            if not found:
                category_list.append({
                    "id": mem_id,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
            self.config_manager.set("instant_memory", memory_dict)
            logger.logger.info(f"即时记忆已添加/覆盖：分类={cata}, ID={mem_id}")
            return True

        elif opt == "del":
            if cata in memory_dict:
                original_len = len(memory_dict[cata])
                memory_dict[cata] = [item for item in memory_dict[cata] if item.get("id") != mem_id]
                if len(memory_dict[cata]) < original_len:
                    self.config_manager.set("instant_memory", memory_dict)
                    logger.logger.info(f"即时记忆已删除：分类={cata}, ID={mem_id}")
                    return True
                else:
                    logger.logger.warning(f"删除失败：分类={cata} 中不存在 ID={mem_id}")
            else:
                logger.logger.warning(f"删除失败：分类={cata} 不存在")
            return False
        else:
            logger.logger.error(f"未知的 instant_memory 操作类型: {opt}")
            return False

    # ---------- 显示AI响应（线程安全）----------
    def display_ai_response(self, response):
        try:
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response

            zh_text = response_data.get("zh", "")
            ja_text = response_data.get("ja", "")
            display_text = zh_text

            # 注意：gui.show_bilingual 是 PyQt 控件，必须在主线程访问
            # 由于该方法可能在工作线程调用，需要将读取控件属性的操作也转到主线程
            # 为了简化，我们使用信号获取该属性值（同步等待），但会增加复杂度。
            # 实际使用中，该复选框状态很少改变，可以缓存其值或通过信号通知。
            # 这里采用安全方式：直接在主线程执行整个显示逻辑
            def show_message():
                if self.gui.show_bilingual.isChecked() and ja_text:
                    final_text = f"{zh_text}\n\n{ja_text}"
                else:
                    final_text = zh_text
                self.gui.add_message(bot_name, final_text, is_user=False)

            self.gui_request.emit(show_message, ())

            if self.gui.generate_audio.isChecked() and ja_text:
                def play_audio():
                    while self.audio_handler.is_playing():
                        time.sleep(0.2)
                    self.audio_handler.play_japanese_audio(ja_text)
                threading.Thread(target=play_audio, daemon=True).start()

            logger.logger.debug(f"成功显示消息：{display_text}")

        except Exception as e:
            self._gui_show_error(f"显示消息时出错: {str(e)}")
            logger.logger.error(f"显示消息时出错: {str(e)}")

    # ---------- 设置最大上下文 ----------
    def set_max_context(self):
        try:
            max_context = int(self.gui.max_context_var.text())
            self._set_busy_state(True)
            self.ai.set_now_max_context(max_context)
            self.ai.set_base_max_context(max_context)
            self._gui_show_info("最大上下文长度已更新")
            logger.logger.info(f"最大上下文长度已更新：{max_context}")
        except ValueError:
            self._gui_show_error("请输入有效的整数")
            logger.logger.error("用户输入的最大上下文长度不是有效的整数")
        except Exception as e:
            self._gui_show_error(f"设置最大上下文时出错: {str(e)}")
        finally:
            self._set_busy_state(False)

    def set_temperature(self):
        try:
            temperature = float(self.gui.temperature_var.text())
            if not 0 <= temperature <= 2:
                raise ValueError("温度值应在0到2之间")
            self._set_busy_state(True)
            self.ai.set_temperature(temperature)
            self._gui_show_info("温度参数已更新")
            logger.logger.info(f"温度已更新：{temperature}")
        except ValueError as e:
            self._gui_show_error(str(e))
        except Exception as e:
            self._gui_show_error(f"设置温度参数时出错: {str(e)}")
        finally:
            self._set_busy_state(False)

    # ---------- 命令处理 ----------
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
            logger.logger.debug(f"开始执行系统命令：{cmd}")
            cmd_name = cmd["cmd"]
            if cmd_name == "talk_to_user":
                if isinstance(cmd["para"], list):
                    for item in cmd["para"]:
                        if isinstance(item, dict) and "zh" in item and "ja" in item:
                            self.display_ai_response(item)
            elif cmd_name == "delay":
                time.sleep(cmd["para"])
            elif cmd_name == "instant_memory":
                para = cmd.get("para", {})
                opt = para.get("opt")
                cata = para.get("cata")
                mem_id = para.get("id")
                content = para.get("content")
                if not opt or not cata or mem_id is None:
                    logger.logger.warning(f"instant_memory 参数不完整: {para}")
                    return
                if opt == "add" and content is None:
                    logger.logger.warning("add 操作缺少 content 字段")
                    return
                # 注意：此时已经持有 self.lock（由 process_user_message 或 process_auto_message 保证）
                self._modify_instant_memory(opt, cata, mem_id, content)
            elif cmd_name == "reset_auto_timer":
                new_interval = cmd.get("para")
                if isinstance(new_interval, int):
                    self.reset_auto_message_timer(new_interval)
                else:
                    logger.logger.warning(f"reset_auto_timer 参数类型错误：{new_interval}")
        except Exception as e:
            logger.logger.error(f"系统命令执行失败：{str(e)}")

    # ---------- 忙碌状态管理（线程安全，GUI操作通过信号）----------
    def _set_busy_state(self, busy: bool):
        """内部方法，调用前必须已持有 self.lock"""
        if busy:
            self._gui_set_status("正忙...")
            self._gui_toggle_widgets_state(False)
        else:
            self._gui_set_status("就绪")
            self._gui_toggle_widgets_state(True)

    # ---------- 清理资源 ----------
    def cleanup(self):
        self._stop_auto_timer()
        if self.audio_handler:
            self.audio_handler.cleanup()
        logger.logger.info("ChatCore安全退出完成")