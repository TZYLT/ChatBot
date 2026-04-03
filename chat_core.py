from enum import auto
from multiprocessing import process
import threading
import time
import datetime
import json
from PyQt5.QtCore import Qt
from AIHandler import aihandler
from datetime import datetime
from ToolsHandler import ToolInvoker
import logger
from typing import List, Dict

user_name = "User"
bot_name = "ChatBot"
auto_msg_time = 15 * 60  # 15分钟

class ChatCore:
    def __init__(self, audio_handler):
        self.gui = None
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.Lock()
        self.auto_message_running = True
        self.tools_handler = ToolInvoker()
        logger.logger.info("ChatCore初始化完成")
        
    def set_gui(self, gui):
        self.gui = gui
        self.gui.max_context_var.setText(str(self.ai.get_now_max_context()))
        self.gui.temperature_var.setText(str(self.ai.get_temperature()))
        logger.logger.info("GUI注入完成")
        self.start_auto_message_thread()
        logger.logger.info("自动消息线程启动成功")
    
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
        # 子线程处理逻辑
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()
    
    def get_tool_responses_info(self):
        tool_responses = self.tools_handler.get_responses()
        if not tool_responses:
            return "[无工具返回信息]"
        response_parts = []
        for resp in tool_responses:
            status = "已完成" if resp['response'] != "Waiting for responses." else "等待中"
            response_parts.append(f"[{resp['name']}:{status}]")
        return "".join(response_parts)
    
    def message_format(self, message):
        tool_info = self.get_tool_responses_info()
        time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if message:
            return f"[{time_str}]{tool_info}[用户发送消息：\"{message}\"]"
        return f"[{time_str}]{tool_info}[自动消息触发]"

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
    
    def start_auto_message_thread(self):
        def auto_message_loop():
            while self.auto_message_running:
                time.sleep(auto_msg_time)
                if not self.auto_message_running:
                    break
                self.gui.process_auto_message_signal.emit()
        
        threading.Thread(target=auto_message_loop, daemon=True).start()
    
    def process_auto_message(self):
        logger.logger.debug("触发自动消息请求")
        if self.lock.locked():
            logger.logger.info("消息线程正在运行，自动消息请求已跳过")
            return
            
        self.set_busy_state(True)
        try:
            formatted_message = self.message_format("")
            commands = self.ai.auto_message(formatted_message)
            self.handle_commands(commands)
            self.gui.add_message("系统", "自动消息:", is_user=False)
        except Exception as e:
            self.gui.show_error(f"自动消息时出错: {str(e)}")
            logger.logger.error(f"自动消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.info("自动消息处理完成")
    
    def display_ai_response(self, response):
        # 【修复】所有UI操作通过信号，子线程安全
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
            
            # UI操作走信号
            self.gui.add_message(bot_name, display_text, is_user=False)
            
            # 【修复】音频播放放到独立线程，不阻塞UI
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
        system_commands = {"talk_to_user", "delay", "instant_memory"}
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
        except Exception as e:
            logger.logger.error(f"系统命令执行失败：{str(e)}")
    
    def set_busy_state(self, busy):
        # 【修复】锁安全 + UI操作走信号
        try:
            if busy:
                self.lock.acquire(timeout=1)  # 避免死锁
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
        self.auto_message_running = False
        if self.audio_handler:
            self.audio_handler.cleanup()
        logger.logger.info("安全退出完成")