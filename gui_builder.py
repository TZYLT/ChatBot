import tkinter as tk
from tkinter import ttk, messagebox
import logger
import os
import json
from datetime import datetime

class ChatGUI:
    def __init__(self, root, message_handler):
        logger.logger.debug("初始化GUI界面")
        self.root = root
        self.message_handler = message_handler
        self.setup_ui()
        # 延迟绑定事件，确保message_handler已设置
        self.setup_event_bindings()
        self.history_file = "chat_history.json"
        # 确保历史文件存在
        if not os.path.exists(self.history_file):
            logger.logger.info("对话历史文件不存在，重新创建对话历史文件")
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        logger.logger.info("GUI界面初始化完成")
    
    def setup_event_bindings(self):
        """单独设置事件绑定，确保message_handler已存在"""
        if hasattr(self, 'user_input') and self.message_handler:
            self.user_input.bind("<Return>", self.message_handler.send_message_event)
            self.send_button.config(command=self.message_handler.send_message)
            self.set_context_button.config(command=self.message_handler.set_max_context)
            self.set_temp_button.config(command=self.message_handler.set_temperature)

    def setup_ui(self):
        """设置GUI界面"""
        self.root.title("ChatBot")
        self.root.geometry("1000x700")
        
        # 主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 聊天显示区域
        self.setup_chat_display(main_frame)
        
        # 用户输入区域
        self.setup_input_area(main_frame)
        
        # 控制面板
        self.setup_control_panel(main_frame)
        
        # 状态栏
        self.setup_status_bar()
    

    def setup_chat_display(self, parent):
        """设置聊天显示区域"""
        self.chat_frame = tk.Frame(parent)
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_text = tk.Text(self.chat_frame, wrap=tk.WORD, state=tk.DISABLED, font=('Microsoft YaHei', 11))
        self.chat_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(self.chat_frame, command=self.chat_text.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.chat_text.config(yscrollcommand=scrollbar.set)
        
        # 配置消息标签样式
        self.chat_text.tag_configure("user_message", 
                                   foreground="blue",
                                   lmargin1=20, lmargin2=20, 
                                   spacing3=10)
        self.chat_text.tag_configure("ai_message", 
                                   foreground="green",
                                   lmargin1=20, lmargin2=20, 
                                   spacing3=10)
    
    def setup_input_area(self, parent):
        """设置用户输入区域"""
        self.input_frame = tk.Frame(parent)
        self.input_frame.pack(fill=tk.X, pady=5)
        
        self.user_input = tk.Text(self.input_frame, height=4, wrap=tk.WORD, font=('Microsoft YaHei', 11))
        self.user_input.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.user_input.bind("<Return>", self.message_handler.send_message_event)
        
        self.send_button = tk.Button(self.input_frame, text="发送", command=self.message_handler.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    def setup_control_panel(self, parent):
        """设置控制面板"""
        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.setup_ai_parameters(control_frame)
        self.setup_display_settings(control_frame)
    
    def setup_ai_parameters(self, parent):
        """设置AI参数设置面板"""
        param_frame = tk.LabelFrame(parent, text="AI参数设置")
        param_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 最大上下文设置
        tk.Label(param_frame, text="最大上下文:").grid(row=0, column=0, padx=(0, 5))
        self.max_context_var = tk.StringVar()
        self.max_context_entry = tk.Entry(param_frame, textvariable=self.max_context_var, width=5)
        self.max_context_entry.grid(row=0, column=1, padx=(0, 10))
        self.set_context_button = tk.Button(param_frame, text="设置", command=self.message_handler.set_max_context)
        self.set_context_button.grid(row=0, column=2, padx=(0, 20))
        
        # 温度参数设置
        tk.Label(param_frame, text="温度参数:").grid(row=0, column=3, padx=(0, 5))
        self.temperature_var = tk.StringVar()
        self.temperature_entry = tk.Entry(param_frame, textvariable=self.temperature_var, width=5)
        self.temperature_entry.grid(row=0, column=4, padx=(0, 10))
        self.set_temp_button = tk.Button(param_frame, text="设置", command=self.message_handler.set_temperature)
        self.set_temp_button.grid(row=0, column=5)
    
    def setup_display_settings(self, parent):
        """设置显示与音频设置面板"""
        display_frame = tk.LabelFrame(parent, text="显示与音频设置")
        display_frame.pack(side=tk.RIGHT, fill=tk.X, padx=5)
        
        self.generate_audio = tk.BooleanVar()
        self.show_bilingual = tk.BooleanVar()
        
        tk.Checkbutton(display_frame, text="生成日语语音", variable=self.generate_audio).grid(row=0, column=0, padx=5)
        tk.Checkbutton(display_frame, text="显示中日双语", variable=self.show_bilingual).grid(row=0, column=1, padx=5)
    
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
    
    def add_message(self, sender, message, is_user=False, save_to_history=True):
        """添加一条消息到聊天显示区域"""
        self.chat_text.config(state=tk.NORMAL)
        tag_name = "user_message" if is_user else "ai_message"
        self.chat_text.insert(tk.END, f"{sender}: \n", "sender_tag")
        self.chat_text.insert(tk.END, f"{message}\n\n", tag_name)
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)
        
        if save_to_history:
            self._save_to_history(sender, message, is_user)

    def _save_to_history(self, sender, message, is_user):
        """将消息保存到历史记录文件中"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
        
        new_entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message,
            "is_user": is_user
        }
        
        history.append(new_entry)
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def load_history(self):
        """加载并显示所有历史消息"""
        # 先清空当前聊天显示
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.config(state=tk.DISABLED)
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
        
        # 加载历史记录时不保存到历史文件(避免重复)
        for entry in history:
            self.add_message(
                sender=entry["sender"],
                message=entry["message"],
                is_user=entry["is_user"],
                save_to_history=False
            )
        logger.logger.info("历史消息加载完成")
    
    def set_status(self, message):
        """设置状态栏消息"""
        self.status_var.set(message)
    
    def toggle_widgets_state(self, state):
        """设置控件状态"""
        widgets = [
            self.user_input, 
            self.send_button, 
            self.max_context_entry, 
            self.set_context_button,
            self.temperature_entry,
            self.set_temp_button
        ]
        for widget in widgets:
            widget.config(state=state)
    
    def show_error(self, message):
        """显示错误信息"""
        messagebox.showerror("错误", message)
    
    def show_info(self, message):
        """显示提示信息"""
        messagebox.showinfo("信息", message)
