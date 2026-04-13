import logging
from datetime import datetime
import sys

def initLogger(name):
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"./logs/{name}_{time_str}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt='[%(asctime)s][%(levelname)s][%(module)s.%(funcName)s:%(lineno)d][%(threadName)-10s]:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 关键修改1：文件处理器强制使用UTF-8编码
    file_handler = logging.FileHandler(filename, encoding='utf-8')
    
    # 关键修改2：控制台处理器处理编码问题
    if sys.stdout.encoding != 'UTF-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:  # Python < 3.7
            sys.stdout = open(sys.stdout.fileno(), mode='w', 
                            encoding='utf-8', buffering=1)
    
    console_handler = logging.StreamHandler()

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = initLogger('ChatBot')