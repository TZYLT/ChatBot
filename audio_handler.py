import os
import tempfile
import threading
import time
import requests
from pygame import mixer

import logger

class AudioHandler:
    def __init__(self):
        logger.logger.debug("初始化音频处理器")
        self.lock = threading.Lock()
        self._initialized = False
        self.initialize_mixer()
        logger.logger.info("音频处理器初始化完成")
    
    def initialize_mixer(self):
        """安全初始化音频混合器"""
        if not self._initialized:
            try:
                logger.logger.debug("初始化音频混合器")
                mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self._initialized = True
                logger.logger.info("音频混合器初始化成功")
            except Exception as e:
                logger.logger.error(f"音频混合器初始化失败: {str(e)}")
    
    def is_playing(self):
        """检查当前是否有音频正在播放"""
        if not self._initialized:
            return False
        
        with self.lock:
            try:
                # 检查是否有活动的音频通道
                return mixer.get_busy()
            except Exception as e:
                logger.logger.error(f"检查播放状态失败: {str(e)}")
                return False
    
    def play_japanese_audio(self, text):
        logger.logger.info(f"音频生成请求: {text}")

        if not self._initialized:
            logger.logger.error("音频处理器未初始化，无法播放音频")
            return
        
        with self.lock:
            temp_file = None
            try:
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"deepseek_audio_{os.getpid()}_{threading.get_ident()}.wav")
                
                logger.logger.debug(f"请求音频生成服务：{text}")
                url = f"http://127.0.0.1:23456/voice/vits?id=4&length=1.2&text={requests.utils.quote(text)}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    with open(temp_file, "wb") as f:
                        f.write(response.content)
                    
                    sound = mixer.Sound(temp_file)
                    channel = sound.play()
                    
                    logger.logger.debug(f"音频生成成功，播放音频\"{temp_file}\"")
                    threading.Thread(
                        target=self._monitor_playback,
                        args=(sound, temp_file, channel),
                        daemon=True
                    ).start()
                
            except Exception as e:
                logger.logger.error(f"音频生成/播放失败: {str(e)}")
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    def _monitor_playback(self, sound_obj, file_path, channel_obj):
        """监控音频播放并清理资源"""
        try:
            while channel_obj.get_busy():
                time.sleep(0.1)
            sound_obj.stop()
            try:
                os.remove(file_path)
                logger.logger.debug(f"音频文件\"{file_path}\"清理成功")
            except Exception as e:
                logger.logger.error(f"音频文件清理失败: {str(e)}")
        except Exception as e:
            logger.logger.error(f"音频播放监控失败: {str(e)}")
            try:
                os.remove(file_path)
            except:
                pass
    
    def cleanup(self):
        """安全清理音频资源"""
        if not self._initialized:
            return
            
        with self.lock:
            try:
                if mixer.get_init() is not None:  # 检查mixer是否已初始化
                    mixer.stop()
                    mixer.quit()
                    self._initialized = False
                    logger.logger.info("音频混合器退出成功")
            except Exception as e:
                logger.logger.error(f"音频混合器退出失败: 未成功清理音频资源，发生错误: {str(e)}")