import os
import tempfile
import threading
import time
import requests
from pygame import mixer

class AudioHandler:
    def __init__(self):
        self.lock = threading.Lock()
        self._initialized = False
        self.initialize_mixer()
    
    def initialize_mixer(self):
        """安全初始化音频混合器"""
        if not self._initialized:
            try:
                mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self._initialized = True
            except Exception as e:
                print(f"初始化音频混合器失败: {str(e)}")
    
    def play_japanese_audio(self, text):
        if not self._initialized:
            return
            
        with self.lock:
            temp_file = None
            try:
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"deepseek_audio_{os.getpid()}_{threading.get_ident()}.wav")
                
                url = f"http://127.0.0.1:23456/voice/vits?id=4&length=1.2&text={requests.utils.quote(text)}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    with open(temp_file, "wb") as f:
                        f.write(response.content)
                    
                    sound = mixer.Sound(temp_file)
                    channel = sound.play()
                    
                    threading.Thread(
                        target=self._monitor_playback,
                        args=(sound, temp_file, channel),
                        daemon=True
                    ).start()
                
            except Exception as e:
                print(f"播放音频时出错: {str(e)}")
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
            except Exception as e:
                print(f"删除临时文件时出错: {str(e)}")
        except Exception as e:
            print(f"音频播放监控出错: {str(e)}")
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
            except Exception as e:
                print(f"清理音频资源时出错: {str(e)}")
