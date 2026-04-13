import logging
import threading
import time
import json
import sys
import traceback
from datetime import datetime
from typing import List, Dict

from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal

from AIHandler import aihandler
from ToolsHandler import ToolInvoker
from config_manager import ConfigManager

# ==================== 日志系统初始化 ====================
def setup_logger():
    """配置全局日志器，保证只初始化一次"""
    logger = logging.getLogger("ChatBot")
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（例如多次导入模块时）
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        fmt='[%(asctime)s][%(levelname)s][%(module)s.%(funcName)s:%(lineno)d][%(threadName)-10s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件 Handler（UTF-8 编码）
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"./logs/ChatBot_{time_str}.log"
    file_handler = logging.FileHandler(filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台 Handler（处理编码问题）
    if sys.stdout.encoding != 'UTF-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:  # Python < 3.7
            sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# 全局 logger 实例
logger = setup_logger()
# ====================================================

user_name = "User"
bot_name = "ChatBot"

class ChatCore(QObject):
    auto_message_trigger = pyqtSignal()
    reset_timer_signal = pyqtSignal(int)
    gui_request = pyqtSignal(object, object)

    def __init__(self, audio_handler):
        super().__init__()
        self.gui = None
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.RLock()
        self.auto_msg_interval = 0
        self.auto_message_executing = False
        self.pending_reset_interval = None

        self.auto_timer = QTimer()
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._on_auto_timer_timeout)

        self.tools_handler = ToolInvoker()
        logger.info("ChatCore 初始化完成")

        self.config_manager = ConfigManager()
        if "instant_memory" not in self.config_manager.get_all():
            self.config_manager.set("instant_memory", {})

        self.auto_message_trigger.connect(self.process_auto_message)
        self.reset_timer_signal.connect(self._reset_auto_timer_slot)
        self.gui_request.connect(self._execute_gui_function)

    def set_gui(self, gui):
        self.gui = gui
        self._gui_set_text(self.gui.max_context_var, str(self.ai.get_now_max_context()))
        self._gui_set_text(self.gui.temperature_var, str(self.ai.get_temperature()))
        logger.info("GUI 注入完成")
        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.info("自动消息间隔为 0，已禁用自动消息")

    # ---------- GUI 线程安全辅助 ----------
    def _execute_gui_function(self, func, args):
        try:
            func(*args)
        except Exception as e:
            logger.error(f"GUI 操作执行失败: {e}\n{traceback.format_exc()}")

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
            logger.debug("用户尝试发送空消息，已忽略")
            return
        self.gui.user_input.clear()
        self._gui_add_message(user_name, message, is_user=True)
        logger.info(f"用户发送消息: {message[:50]}...")  # 避免日志过长
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

    # ---------- 用户消息处理 ----------
    def process_user_message(self, message):
        logger.debug(f"进入用户消息处理线程，消息: {message[:50]}")
        if not self.lock.acquire(timeout=2):
            logger.error("获取锁超时，放弃处理用户消息")
            self._gui_show_error("系统繁忙，请稍后再试")
            return
        try:
            self._set_busy_state(True)
            formatted_message = self.message_format(message)
            logger.debug(f"格式化后的消息: {formatted_message}")
            commands = self.ai.user_message(formatted_message)
            logger.debug(f"AI 返回命令: {commands}")
            self.handle_commands(commands)
        except Exception as e:
            logger.error(f"处理用户消息时出错: {e}\n{traceback.format_exc()}")
            self._gui_show_error(f"发送消息时出错: {str(e)}")
        finally:
            self._set_busy_state(False)
            self.lock.release()
            logger.debug("用户消息处理完成，锁已释放")

    # ---------- 自动消息相关 ----------
    def _start_auto_timer(self):
        self.auto_timer.stop()
        if self.auto_msg_interval > 0:
            self.auto_timer.start(self.auto_msg_interval * 1000)
            logger.debug(f"自动消息定时器启动，间隔 {self.auto_msg_interval} 秒")

    def _stop_auto_timer(self):
        self.auto_timer.stop()
        logger.debug("自动消息定时器已停止")

    def _on_auto_timer_timeout(self):
        logger.debug("自动消息定时器超时，触发自动消息信号")
        self.auto_message_trigger.emit()

    def _schedule_next_auto_message(self):
        if self.pending_reset_interval is not None:
            new_interval = self.pending_reset_interval
            self.pending_reset_interval = None
            if new_interval is not None and new_interval >= 0:
                self.auto_msg_interval = new_interval
                if new_interval == 0:
                    logger.info("自动消息已禁用（间隔设为 0）")
                else:
                    logger.info(f"应用待重置的自动消息间隔：{self.auto_msg_interval} 秒")
            else:
                logger.warning(f"待重置的间隔无效: {new_interval}，忽略")
        if self.auto_msg_interval > 0:
            self.reset_auto_message_timer()
        else:
            logger.debug("自动消息间隔为 0，不再调度下一次自动消息")

    def _reset_auto_timer_slot(self, new_interval: int):
        if self.auto_message_executing:
            if new_interval >= 0:
                self.pending_reset_interval = new_interval
                logger.info(f"自动消息执行中，重置计时器请求已挂起（新间隔：{new_interval} 秒）")
            else:
                self.pending_reset_interval = self.auto_msg_interval
                logger.info("自动消息执行中，重置计时请求已挂起（仅重置倒计时）")
            return

        self._stop_auto_timer()
        if new_interval >= 0:
            self.auto_msg_interval = new_interval
            if new_interval == 0:
                logger.info("自动消息已禁用（间隔设为 0）")
            else:
                logger.info(f"自动消息间隔已更新为 {self.auto_msg_interval} 秒")
        elif new_interval == -1:
            logger.debug("仅重置自动消息计时器，间隔不变")
        else:
            logger.warning(f"无效的自动消息间隔：{new_interval}，保持原间隔")

        if self.auto_msg_interval > 0:
            self._start_auto_timer()
        else:
            logger.debug("自动消息间隔为 0，定时器已停止且不再启动")

    def reset_auto_message_timer(self, new_interval: int = None):
        interval = new_interval if new_interval is not None else -1
        self.reset_timer_signal.emit(interval)

    # ---------- 自动消息处理 ----------
    def process_auto_message(self):
        if self.auto_message_executing:
            logger.info("自动消息正在执行，跳过本次触发")
            return
        logger.debug("启动自动消息处理子线程")
        threading.Thread(target=self._process_auto_message_worker, daemon=True).start()

    def _process_auto_message_worker(self):
        logger.debug("进入自动消息工作线程")
        if not self.lock.acquire(timeout=1):
            logger.warning("自动消息获取锁超时，稍后重试")
            self.reset_auto_message_timer()
            return

        self.auto_message_executing = True
        try:
            self._set_busy_state(True)
            formatted_message = self.message_format("")
            logger.debug(f"自动消息格式化: {formatted_message}")
            commands = self.ai.auto_message(formatted_message)
            logger.debug(f"AI 返回自动消息命令: {commands}")
            self.handle_commands(commands)
            self._gui_add_message("系统", "自动触发消息", is_user=False)
        except Exception as e:
            logger.error(f"自动消息处理出错: {e}\n{traceback.format_exc()}")
            self._gui_show_error(f"自动消息时出错: {str(e)}")
        finally:
            self._set_busy_state(False)
            self.auto_message_executing = False
            self.lock.release()
            self._schedule_next_auto_message()
            logger.info("自动消息处理完成")

    # ---------- 即时记忆管理 ----------
    def _modify_instant_memory(self, opt: str, cata: str, mem_id: int, content: str = None) -> bool:
        self.config_manager.reload()
        memory_dict = self.config_manager.get("instant_memory")
        if not isinstance(memory_dict, dict):
            memory_dict = {}

        logger.debug(f"执行即时记忆操作: opt={opt}, cata={cata}, id={mem_id}, content={content[:50] if content else None}")

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
            logger.info(f"即时记忆已添加/覆盖：分类={cata}, ID={mem_id}")
            return True

        elif opt == "del":
            if cata in memory_dict:
                original_len = len(memory_dict[cata])
                memory_dict[cata] = [item for item in memory_dict[cata] if item.get("id") != mem_id]
                if len(memory_dict[cata]) < original_len:
                    self.config_manager.set("instant_memory", memory_dict)
                    logger.info(f"即时记忆已删除：分类={cata}, ID={mem_id}")
                    return True
                else:
                    logger.warning(f"删除失败：分类={cata} 中不存在 ID={mem_id}")
            else:
                logger.warning(f"删除失败：分类={cata} 不存在")
            return False
        else:
            logger.error(f"未知的 instant_memory 操作类型: {opt}")
            return False

    # ---------- 显示 AI 响应 ----------
    def display_ai_response(self, response):
        try:
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response

            zh_text = response_data.get("zh", "")
            ja_text = response_data.get("ja", "")
            logger.debug(f"收到 AI 响应: zh={zh_text[:30]}..., ja={ja_text[:30]}...")

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

            logger.info(f"已显示 AI 消息: {zh_text[:50]}...")

        except Exception as e:
            logger.error(f"显示消息时出错: {e}\n{traceback.format_exc()}")
            self._gui_show_error(f"显示消息时出错: {str(e)}")

    # ---------- 设置参数 ----------
    def set_max_context(self):
        try:
            max_context = int(self.gui.max_context_var.text())
            self._set_busy_state(True)
            self.ai.set_now_max_context(max_context)
            self.ai.set_base_max_context(max_context)
            self._gui_show_info("最大上下文长度已更新")
            logger.info(f"最大上下文长度已更新：{max_context}")
        except ValueError:
            logger.error("用户输入的最大上下文长度不是有效的整数")
            self._gui_show_error("请输入有效的整数")
        except Exception as e:
            logger.error(f"设置最大上下文时出错: {e}\n{traceback.format_exc()}")
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
            logger.info(f"温度已更新：{temperature}")
        except ValueError as e:
            logger.warning(f"温度设置参数错误: {e}")
            self._gui_show_error(str(e))
        except Exception as e:
            logger.error(f"设置温度参数时出错: {e}\n{traceback.format_exc()}")
            self._gui_show_error(f"设置温度参数时出错: {str(e)}")
        finally:
            self._set_busy_state(False)

    # ---------- 命令处理 ----------
    def handle_commands(self, commands: List[Dict]) -> None:
        logger.debug(f"开始处理来自 AI 请求的命令，共 {len(commands)} 条")
        for cmd in commands:
            if self.is_system_command(cmd):
                self.execute_system_command(cmd)
            else:
                self.tools_handler.add_tasks([cmd])
        logger.info("AI 请求的命令已处理完成")

    def is_system_command(self, cmd: Dict) -> bool:
        system_commands = {"talk_to_user", "delay", "instant_memory", "reset_auto_timer"}
        return cmd.get("cmd") in system_commands

    def execute_system_command(self, cmd: Dict):
        try:
            logger.debug(f"执行系统命令: {cmd}")
            cmd_name = cmd["cmd"]
            if cmd_name == "talk_to_user":
                if isinstance(cmd["para"], list):
                    for item in cmd["para"]:
                        if isinstance(item, dict) and "zh" in item and "ja" in item:
                            self.display_ai_response(item)
            elif cmd_name == "delay":
                delay_sec = cmd["para"]
                logger.debug(f"延迟 {delay_sec} 秒")
                time.sleep(delay_sec)
            elif cmd_name == "instant_memory":
                para = cmd.get("para", {})
                opt = para.get("opt")
                cata = para.get("cata")
                mem_id = para.get("id")
                content = para.get("content")
                if not opt or not cata or mem_id is None:
                    logger.warning(f"instant_memory 参数不完整: {para}")
                    return
                if opt == "add" and content is None:
                    logger.warning("add 操作缺少 content 字段")
                    return
                self._modify_instant_memory(opt, cata, mem_id, content)
            elif cmd_name == "reset_auto_timer":
                new_interval = cmd.get("para")
                if isinstance(new_interval, int):
                    self.reset_auto_message_timer(new_interval)
                else:
                    logger.warning(f"reset_auto_timer 参数类型错误：{new_interval}")
        except Exception as e:
            logger.error(f"系统命令执行失败: {e}\n{traceback.format_exc()}")

    # ---------- 忙碌状态管理 ----------
    def _set_busy_state(self, busy: bool):
        if busy:
            logger.debug("切换至忙碌状态")
            self._gui_set_status("正忙...")
            self._gui_toggle_widgets_state(False)
        else:
            logger.debug("切换至就绪状态")
            self._gui_set_status("就绪")
            self._gui_toggle_widgets_state(True)

    # ---------- 清理资源 ----------
    def cleanup(self):
        self._stop_auto_timer()
        if self.audio_handler:
            self.audio_handler.cleanup()
        logger.info("ChatCore 安全退出完成")