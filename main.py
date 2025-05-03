import tkinter as tk
from audio_handler import AudioHandler
from gui_builder import ChatGUI
from chat_core import ChatCore

def main():
    root = tk.Tk()
    
    try:
        # 初始化各模块
        audio_handler = AudioHandler()
        chat_core = ChatCore(audio_handler)
        gui = ChatGUI(root, chat_core)
        chat_core.set_gui(gui)
        
        # 设置关闭事件处理
        def on_closing():
            try:
                chat_core.cleanup()
            finally:
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        root.mainloop()
    except Exception as e:
        print(f"应用程序错误: {str(e)}")
        audio_handler.cleanup()
        root.destroy()

if __name__ == "__main__":
    main()
