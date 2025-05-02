import logging
from datetime import datetime

def initLogger(name):
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"./logs/{name}_{time_str}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt='[%(module)s][%(levelname)s][%(asctime)s]:%(message)s',
                                        datefmt='%Y-%m-%d %H:%M:%S',)
    
    file_handler = logging.FileHandler(filename)
    console_handler = logging.StreamHandler()

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = initLogger('ChatBot')
