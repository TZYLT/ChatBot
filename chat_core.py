import threading
import time
import json
from AIHandler import aihandler
import tkinter as tk

class ChatCore:
    def __init__(self, audio_handler):
        self.gui = None  # 稍后通过set_gui注入
        self.audio_handler = audio_handler
        self.ai = aihandler()
        self.lock = threading.Lock()
        self.auto_message_running = True
        
    def set_gui(self, gui):
        self.gui = gui
        # 初始化GUI变量
        self.gui.max_context_var.set(str(self.ai.get_max_context()))
        self.gui.temperature_var.set(str(self.ai.get_temperature()))
        # 启动自动消息线程
        self.start_auto_message_thread()
    
    def send_message_event(self, event):
        if not event.state & 0x0001:  # 检查Shift键是否按下
            self.send_message()
            return "break"
        return None
    
    def send_message(self):
        message = self.gui.user_input.get("1.0", tk.END).strip()
        if not message:
            return
            
        self.gui.user_input.delete("1.0", tk.END)
        self.gui.add_message("用户", message, is_user=True)
        
        threading.Thread(target=self.process_user_message, args=(message,), daemon=True).start()
    
    def process_user_message(self, message):
        self.set_busy_state(True)
        try:
            responses = self.ai.user_message(message)
            self.display_ai_responses(responses)
        except Exception as e:
            self.gui.show_error(f"发送消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
    
    def start_auto_message_thread(self):
        def auto_message_loop():
            while self.auto_message_running:
                time.sleep(15 * 60)  # 15分钟
                if not self.auto_message_running:
                    break
                    
                self.gui.root.after(0, self.process_auto_message)
        
        threading.Thread(target=auto_message_loop, daemon=True).start()
    
    def process_auto_message(self):
        if self.lock.locked():
            return
            
        self.set_busy_state(True)
        try:
            responses = self.ai.auto_message()
            if responses:
                self.gui.add_message("系统", "自动消息:", is_user=False)
                self.display_ai_responses(responses)
        except Exception as e:
            self.gui.show_error(f"自动消息时出错: {str(e)}")
        finally:
            self.set_busy_state(False)
    
    def display_ai_responses(self, responses):
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
                    threading.Thread(
                        target=self.audio_handler.play_japanese_audio, 
                        args=(ja_text,),
                        daemon=True
                    ).start()
                    
            except (json.JSONDecodeError, AttributeError):
                self.gui.add_message("AI助手", str(response), is_user=False)
            except Exception as e:
                self.gui.show_error(f"显示消息时出错: {str(e)}")
    
    def set_max_context(self):
        try:
            max_context = int(self.gui.max_context_var.get())
            self.set_busy_state(True)
            try:
                self.ai.set_max_context(max_context)
                self.gui.show_info("最大上下文长度已更新")
            except Exception as e:
                self.gui.show_error(f"设置最大上下文时出错: {str(e)}")
            finally:
                self.set_busy_state(False)
        except ValueError:
            self.gui.show_error("请输入有效的整数")
    
    def set_temperature(self):
        try:
            temperature = float(self.gui.temperature_var.get())
            if not 0 <= temperature <= 2:
                raise ValueError("温度值应在0到2之间")
                
            self.set_busy_state(True)
            try:
                self.ai.set_temperature(temperature)
                self.gui.show_info("温度参数已更新")
            except Exception as e:
                self.gui.show_error(f"设置温度参数时出错: {str(e)}")
            finally:
                self.set_busy_state(False)
        except ValueError as e:
            self.gui.show_error(str(e))
    
    def set_busy_state(self, busy):
        if busy:
            self.lock.acquire()
            self.gui.set_status("正忙...")
            self.gui.toggle_widgets_state(tk.DISABLED)
        else:
            self.gui.set_status("就绪")
            self.gui.toggle_widgets_state(tk.NORMAL)
            if self.lock.locked():
                self.lock.release()
        
        self.gui.root.update()
    
    def cleanup(self):
        """安全的清理过程"""
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
