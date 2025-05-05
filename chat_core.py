from enum import auto
from multiprocessing import process
import threading
import time
import datetime
import json
import tkinter as tk
from AIHandler import aihandler
from datetime import datetime
from chat_memory.memory_handler import MemoryHandler


import logger

from typing import List, Dict
import tools.CmdExecutor

user_name = "AI助手"

bot_name = "ChatBot"

auto_msg_time = 15 * 60  # 15分钟


class ChatCore:
    def __init__(self, audio_handler):
        """初始化ChatCore"""
        logger.logger.debug("初始化ChatCore")
        self.gui = None  # 稍后通过set_gui注入
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.Lock()
        self.auto_message_running = True
        self.next_turn_return_msg = []
        self.memroies = MemoryHandler()
        
        logger.logger.info("ChatCore初始化完成")
        
    def set_gui(self, gui):
        """注入GUI"""
        logger.logger.debug("注入GUI")
        self.gui = gui
        # 初始化GUI变量
        self.gui.max_context_var.set(str(self.ai.get_max_context()))
        self.gui.temperature_var.set(str(self.ai.get_temperature()))
        logger.logger.info("GUI注入完成")

        # 启动自动消息线程
        self.start_auto_message_thread()
        logger.logger.info("自动消息线程启动成功")
    
    def send_message_event(self, event):
        """发送消息事件"""
        if not event.state & 0x0001:  # 检查Shift键是否按下
            self.send_message()
            return "break"
        return None
    
    def send_message(self):
        """发送用户消息"""
        message = self.gui.user_input.get("1.0", tk.END).strip()
        if not message:
            return
            
        self.gui.user_input.delete("1.0", tk.END)
        self.gui.add_message(user_name, message, is_user=True)
        
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()
    
    def message_format(self, message):
        """格式化消息"""
        if self.next_turn_return_msg:
            message = f"[上一次请求命令返回消息：{self.next_turn_return_msg}][用户发送消息：\"{message}\"]"
            self.next_turn_return_msg = []
        else:
            message = f"[无上一次请求命令返回消息][用户发送消息：\"{message}\"]"

        time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        message = f"[{time_str}][{message}]"

        return message

    def process_user_message(self, message):
        """处理用户消息"""
        logger.logger.info(f"处理用户消息请求：{message}")
        self.set_busy_state(True)
        message = self.message_format(message)

        try:
            commands = self.ai.user_message(message)
            self.handle_commands(commands)
        except Exception as e:
            self.gui.show_error(f"发送消息时出错: {str(e)}")
            logger.logger.error(f"发送消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.debug(f"处理用户消息完成")
    
    def process_cmd_message(self, message : str):
        """处理命令消息"""
        if not message:
            logger.logger.warning("命令消息为空，忽略")
            return
        
        logger.logger.info(f"处理命令消息请求：{message}")

        time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        message = f"[{time_str}][命令返回信息：\"{message}\"]"

        try:
            commands = self.ai.cmd_message(message)
            self.handle_commands(commands)
        except Exception as e:
            self.gui.show_error(f"发送消息时出错: {str(e)}")
            logger.logger.error(f"发送消息时出错: {str(e)}")
        finally:
            logger.logger.debug(f"处理命令消息完成")
    
    def start_auto_message_thread(self):
        """启动自动消息线程"""
        def auto_message_loop():
            while self.auto_message_running:
                time.sleep(auto_msg_time)
                if not self.auto_message_running:
                    break
                    
                self.gui.root.after(0, self.process_auto_message)
        
        threading.Thread(target=auto_message_loop, daemon=True).start()
    
    def process_auto_message(self):
        """处理自动消息"""
        logger.logger.debug("触发自动消息请求")
        if self.lock.locked():
            logger.logger.info("消息线程正在运行，自动消息请求已跳过")
            return
            
        self.set_busy_state(True)

        message = ""
        message = self.message_format(message)

        try:
            commands = self.ai.auto_message(message)
            self.handle_commands(commands)
            self.gui.add_message("系统", "自动消息:", is_user=False)
        except Exception as e:
            self.gui.show_error(f"自动消息时出错: {str(e)}")
            logger.logger.error(f"自动消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.info("自动消息处理完成")
    
    def display_ai_response(self, response):
        """显示AI响应并按顺序播放音频"""
        try:
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response
            
            zh_text = response_data.get("zh", "")
            ja_text = response_data.get("ja", "")
            
            display_text = zh_text
            if self.gui.show_bilingual.get() and ja_text:
                display_text = f"{zh_text}\n\n{ja_text}"
            
            self.gui.add_message(bot_name, display_text, is_user=False)
            
            if self.gui.generate_audio.get() and ja_text:
                # 等待当前音频播放完成
                while self.audio_handler.is_playing():
                    time.sleep(0.2)
                
                # 播放当前音频
                self.audio_handler.play_japanese_audio(ja_text)

            logger.logger.debug(f"成功显示消息：{display_text}")
                
        except (json.JSONDecodeError, AttributeError):
            self.gui.add_message("AI助手", str(response), is_user=False)
            logger.logger.error(f"显示消息时出错: 响应格式不正确：{response}")
        except Exception as e:
            self.gui.show_error(f"显示消息时出错: {str(e)}")
            logger.logger.error(f"显示消息时出错: {str(e)}")
    
    def set_max_context(self):
        """设置最大上下文长度"""
        try:
            max_context = int(self.gui.max_context_var.get())
            self.set_busy_state(True)
            try:
                self.ai.set_max_context(max_context)
                self.gui.show_info("最大上下文长度已更新")
                logger.logger.info(f"最大上下文长度已更新：{max_context}")
            except Exception as e:
                self.gui.show_error(f"设置最大上下文时出错: {str(e)}")
                logger.logger.error(f"设置最大上下文时出错: {str(e)}")
            finally:
                self.set_busy_state(False)
        except ValueError:
            self.gui.show_error("请输入有效的整数")
            logger.logger.error("用户输入的最大上下文长度不是有效的整数")
    
    def set_temperature(self):
        """设置AI的温度"""
        try:
            temperature = float(self.gui.temperature_var.get())
            if not 0 <= temperature <= 2:
                raise ValueError("温度值应在0到2之间")
                
            self.set_busy_state(True)
            try:
                self.ai.set_temperature(temperature)
                self.gui.show_info("温度参数已更新")
                logger.logger.info(f"温度已更新：{temperature}")
            except Exception as e:
                self.gui.show_error(f"设置温度参数时出错: {str(e)}")
                logger.logger.error(f"设置温度时出错: {str(e)}")
            finally:
                self.set_busy_state(False)
        except ValueError as e:
            self.gui.show_error(str(e))
            logger.logger.error(f"用户输入的温度值不是有效的浮点数: {str(e)}")

    def handle_commands(self, commands: List[Dict]) -> None:
        """处理命令并返回需要展示的内容"""
        logger.logger.debug(f"开始处理来自AI请求的命令：{commands}")
        return_afterall = []

        for cmd in commands:
            if cmd["return_method"] == "immediately":
                cmd_response = self.cmd_executor(cmd)
                if cmd_response:
                    self.process_cmd_message(cmd_response)
            elif cmd["return_method"] == "afterall":
                cmd_response = self.cmd_executor(cmd)
                if cmd_response:
                    return_afterall.append(cmd_response)
            elif cmd["return_method"] == "next_turn":
                cmd_response = self.cmd_executor(cmd)
                if cmd_response:
                    self.next_turn_return_msg.append(cmd_response)
            elif cmd["return_method"] == "none":
                self.cmd_executor(cmd)
            else:
                logger.logger.warning(f"未知的return_method，默认为none：{cmd}")
                self.cmd_executor(cmd)

        logger.logger.info(f"来自AI请求的命令已处理完成")
    
    def cmd_executor(self, cmd: Dict) -> str:
        """命令执行器"""
        try:
            logger.logger.info(f"开始执行命令：{cmd}")
            if cmd["cmd"] == "talk_to_user":
                # AI请求与用户对话
                if isinstance(cmd["para"], list):
                    for item in cmd["para"]:
                        if isinstance(item, dict) and "zh" in item and "ja" in item:
                            self.display_ai_response(item)
                return ""
            elif cmd["cmd"] == "cmd_processor":
                # cmd命令执行器
                logger.logger.debug(f"AI请求执行cmd命令")
                return tools.CmdExecutor.run_command_with_approval(cmd["para"])
            elif cmd["cmd"] == "delay":
                # 延时
                time.sleep(cmd["para"])
                return ""
            elif cmd["cmd"] == "add_memory":
                # 添加记忆
                logger.logger.debug(f"AI请求添加记忆：{cmd['para']}")
                self.memroies.add_memory(**cmd["para"])
                return ""
            elif cmd["cmd"] == "read_memories":
                # 读取记忆
                logger.logger.debug(f"AI请求读取记忆：{cmd['para']}")
                cmd["para"]["start_time"] = datetime.strptime(cmd["para"]["start_time"], "%Y-%m-%dT%H:%M:%S")
                cmd["para"]["end_time"] = datetime.strptime(cmd["para"]["end_time"], "%Y-%m-%dT%H:%M:%S")
                return_memories = self.memroies.read_memories(**cmd["para"])
                return f"读取到的记忆：{return_memories}"
            else:
                logger.logger.warning(f"未知命令：{cmd}")
                return ""
        except Exception as e:
            logger.logger.error(f"命令执行失败：{str(e)}")
            return ""
    
    def set_busy_state(self, busy):
        """设置忙碌状态"""
        if busy:
            self.lock.acquire()
            self.gui.set_status("正忙...")
            self.gui.toggle_widgets_state(tk.DISABLED)
            logger.logger.debug("进入忙碌状态")
        else:
            self.gui.set_status("就绪")
            self.gui.toggle_widgets_state(tk.NORMAL)
            if self.lock.locked():
                self.lock.release()
                logger.logger.debug("退出忙碌状态")
        
        self.gui.root.update()
    
    def cleanup(self):
        """安全的清理过程"""
        logger.logger.debug("开始安全退出")
        self.auto_message_running = False
        
        # 确保GUI已销毁后再清理音频
        if hasattr(self, 'gui') and self.gui and hasattr(self.gui, 'root'):
            try:
                self.gui.root.update()  # 确保所有GUI操作完成
            except:
                pass
        
        # 安全清理音频
        if hasattr(self, 'audio_handler') and self.audio_handler:
            self.audio_handler.cleanup()
        logger.logger.info("安全退出完成")

