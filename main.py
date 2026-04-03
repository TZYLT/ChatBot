import sys
from PyQt5.QtWidgets import QApplication
from audio_handler import AudioHandler
from pyqt_gui import ChatGUI
from chat_core import ChatCore
import logger

def main():
    # 初始化PyQt5应用
    app = QApplication(sys.argv)
    
    try:
        # 初始化各模块（与原逻辑完全一致）
        logger.logger.debug("开始初始化各模块")
        audio_handler = AudioHandler()
        chat_core = ChatCore(audio_handler)
        # 创建PyQt5 GUI
        gui = ChatGUI(chat_core)
        chat_core.set_gui(gui)
        logger.logger.info("各模块初始化完成")

        # 显示窗口
        gui.show()

        # 重写窗口关闭事件（替代原Tk的WM_DELETE_WINDOW）
        def close_event(event):
            try:
                chat_core.cleanup()
                logger.logger.info("程序正常退出，资源成功释放")
            finally:
                event.accept()
        
        gui.closeEvent = close_event

        # 启动PyQt5事件循环
        sys.exit(app.exec_())

    except Exception as e:
        logger.logger.error(f"程序异常退出，发生错误：{str(e)}")
        # 异常时清理音频资源
        if 'audio_handler' in locals():
            audio_handler.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()