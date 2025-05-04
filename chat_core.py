import threading
import time
import json

from setuptools import Command
from AIHandler import aihandler
import tkinter as tk
import logger

from typing import List, Dict
import tools.CmdExecutor

class ChatCore:
    def __init__(self, audio_handler):
        """初始化ChatCore"""
        logger.logger.debug("初始化ChatCore")
        self.gui = None  # 稍后通过set_gui注入
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.Lock()
        self.auto_message_running = True
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
        self.gui.add_message("用户", message, is_user=True)
        
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()
    
    def process_user_message(self, message):
        """处理用户消息"""
        logger.logger.info(f"处理用户消息请求：{message}")
        self.set_busy_state(True)
        try:
            commands = self.ai.user_message(message)
            responses = self._handle_commands(commands)

            self.display_ai_responses(responses)
        except Exception as e:
            self.gui.show_error(f"发送消息时出错: {str(e)}")
            logger.logger.error(f"发送消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.debug(f"处理用户消息完成")
    
    def start_auto_message_thread(self):
        """启动自动消息线程"""
        def auto_message_loop():
            while self.auto_message_running:
                time.sleep(15 * 60)  # 15分钟
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
        try:
            commands = self.ai.auto_message("")
            responses = self._handle_commands(commands)
            if responses:
                self.gui.add_message("系统", "自动消息:", is_user=False)
                self.display_ai_responses(responses)
        except Exception as e:
            self.gui.show_error(f"自动消息时出错: {str(e)}")
            logger.logger.error(f"自动消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
            logger.logger.debug("自动消息处理完成")
    
    def display_ai_responses(self, responses):
        """显示AI响应并按顺序播放音频"""
        for response in responses:
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
                
                self.gui.add_message("AI助手", display_text, is_user=False)
                
                if self.gui.generate_audio.get() and ja_text:
                    # 等待当前音频播放完成
                    while self.audio_handler.is_playing():  # 假设audio_handler有is_playing方法
                        time.sleep(0.1)
                    
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

    def _handle_commands(self, commands: List[Dict]) -> List[Dict]:
        """处理命令并返回需要展示的内容"""
        logger.logger.debug(f"开始处理来自AI请求的命令：{commands}")
        user_messages = []
        for cmd in commands:
            if cmd["cmd"] == "talk_to_user":
                # 确保para是双语字典列表
                if isinstance(cmd["para"], list):
                    for item in cmd["para"]:
                        if isinstance(item, dict) and "zh" in item and "ja" in item:
                            user_messages.append(item)
            else:
                self.cmd_executor(cmd)
        logger.logger.info(f"来自AI请求的命令已处理完成")
        return user_messages
    
    def cmd_executor(self, cmd: Dict):
        """命令执行器"""
        logger.logger.info(f"开始执行命令：{cmd}")
        if cmd["cmd"] == "cmd_processor":
            # 处理命令
            logger.logger.debug(f"AI请求执行cmd命令")
            tools.CmdExecutor.run_command_with_approval(cmd["para"])
        else:
            logger.logger.warning(f"未知命令：{cmd}")
    
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
