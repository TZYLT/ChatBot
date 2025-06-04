import json
import re
import openai
import tools.CmdExecutor as CmdExecutor
import logger
from math import sqrt
from typing import List, Dict

auto_api_usage_economizer = True # 是否开启自动API节约算法

class aihandler:
    def __init__(self):
        # 新增响应标记匹配模式
        self.response_tag_regex = re.compile(
            r'<response>(.*)',  # 匹配<response>后的所有内容
            re.DOTALL  # 允许跨行匹配
        )
        logger.logger.info("AI处理器初始化完成")
    
    def _get_config(self) -> Dict:
        """从config.json读取最新配置"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                logger.logger.debug("重新读取配置文件成功")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.logger.warning("配置文件不存在或格式错误，创建新配置文件")
            return {
                "apikey": "", 
                "temperature": 0.5, 
                "base_max_context": 10, 
                "now_max_context": 10, 
                "system_prompt": "",
                "instant_memory": "",
                "model": 'deepseek_chat'
            }
    
    def _save_history(self, message: List[Dict]):
        """保存历史记录（不包含第一条系统提示词）"""
        # 过滤掉第一条系统提示词
        try:
            with open('history.json', 'r', encoding='utf-8') as f:
                saved_dialog = json.load(f)
            to_save = saved_dialog + message
        except (FileNotFoundError, json.JSONDecodeError):
            to_save = message
        
        with open('history.json', 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=4)
        logger.logger.debug("历史记录已保存")

    def _load_history(self) -> List[Dict]:
        """加载历史记录并动态合并最新系统提示词"""
        config = self._get_config()
        try:
            # 读取保存的对话记录（不包含初始系统提示词）
            with open('history.json', 'r', encoding='utf-8') as f:
                saved_dialog = json.load(f)
            
            # 创建新历史记录结构
            new_history = [
                {"role": "system", "content": config["system_prompt"]},  # 最新系统提示词
                {"role": "system", "content": f"[保存的即时记忆]{config["instant_memory"]}"},  # 短期记忆
                *saved_dialog  # 保存的完整对话记录
            ]

            # 截断处理（保留系统提示词和最新对话）
            max_ctx = config.get("now_max_context", 10)
            keep_from = max(-(max_ctx-1), -len(new_history)+1)  # 确保至少保留系统提示词
            final_history = [new_history[0]] + new_history[keep_from:]

            logger.logger.info(f"历史记录已加载，保留最新{max_ctx}条")
            return final_history
        except (FileNotFoundError, json.JSONDecodeError):
            logger.logger.warning("历史记录文件不存在或格式错误，创建新历史记录")
            return [{"role": "system", "content": config["system_prompt"]}]
    
    def set_base_max_context(self, base_max_context: int):
        """设置基础最大上下文长度并保存到config.json"""
        try:
            # 读取现有配置
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新配置
            config['base_max_context'] = base_max_context
            
            # 写回文件
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            logger.logger.info(f"基础最大上下文长度已设置为{base_max_context}，已保存到配置文件")
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，创建新配置
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'apikey': '',
                    'temperature': 0.5,
                    'base_max_context': base_max_context,
                    'now_max_context': base_max_context,
                    'system_prompt': '',
                    'instant_memory': '',
                    "model": "deepseek_chat"
                }, f, ensure_ascii=False, indent=4)
            logger.logger.warning(f"配置文件不存在或格式错误，已创建新配置文件，最大上下文长度已设置为{base_max_context}")
    
    def get_base_max_context(self):
        return self._get_config().get("base_max_context", 10)
    
    def set_now_max_context(self, now_max_context: int):
        """设置当前最大上下文长度并保存到config.json"""
        try:
            # 读取现有配置
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新配置
            config['now_max_context'] = now_max_context
            
            # 写回文件
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            logger.logger.info(f"当前最大上下文长度已设置为{now_max_context}，已保存到配置文件")
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，创建新配置
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'apikey': '',
                    'temperature': 0.5,
                    'base_max_context': now_max_context,
                    'now_max_context': now_max_context,
                    'system_prompt': '',
                    'instant_memory': '',
                    "model": "deepseek_chat"
                }, f, ensure_ascii=False, indent=4)
            logger.logger.warning(f"配置文件不存在或格式错误，已创建新配置文件，最大上下文长度已设置为{now_max_context}")
    
    def get_now_max_context(self):
        return self._get_config().get("now_max_context", 10)
    
    def set_temperature(self, temperature: float):
        """设置温度参数并保存到config.json"""
        try:
            # 读取现有配置
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新配置
            config['temperature'] = temperature
            
            # 写回文件
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

            logger.logger.info(f"AI温度已设置为{temperature}，已保存到配置文件")
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，创建新配置
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'apikey': '',
                    'temperature': temperature,
                    'base_max_context': 10,
                    'now_max_context': 10,
                    'system_prompt': '',
                    'instant_memory': '',
                    "model": "deepseek_chat"
                }, f, ensure_ascii=False, indent=4)
            logger.logger.warning(f"配置文件不存在或格式错误，已创建新配置文件，温度已设置为{temperature}")
               
    def get_temperature(self):
        return self._get_config().get("temperature", 0.5)
    
    def set_instant_memory(self, instant_memory: str):
        """设置短时记忆模式到config.json"""
        try:
            # 读取现有配置
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新配置
            config['instant_memory'] = instant_memory
            
            # 写回文件
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

            logger.logger.info(f"即时记忆已更新为{instant_memory}，已保存到配置文件")
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，创建新配置
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'apikey': '',
                    'temperature': 0.5,
                    'base_max_context': 10,
                    'now_max_context': 10,
                    'system_prompt': '',
                    'instant_memory': instant_memory,
                    "model": "deepseek_chat"
                }, f, ensure_ascii=False, indent=4)
            logger.logger.warning(f"配置文件不存在或格式错误，已创建新配置文件，即时记忆已设置为{instant_memory}")
               
    def get_instant_memory(self):
        return self._get_config().get("instant_memory", "无")
    
    def update_max_context(self, add_context_length: int):
        """自动更新最大上下文长度以节省API成本"""
        now_max_context = self.get_now_max_context()
        base_max_context = self.get_base_max_context()
        
        max_context_limit = base_max_context + 2 * int(sqrt(3 * base_max_context + 2) -1)
        
        if now_max_context < max_context_limit:
            now_max_context += add_context_length
        else:
            now_max_context = base_max_context
        self.set_now_max_context(now_max_context)
        logger.logger.info(f"最大上下文长度已自动更新为{now_max_context}")
    
    def _call_api(self, messages: List[Dict]) -> str:
        """调用DeepSeek API"""
        config = self._get_config()
        client = openai.OpenAI(api_key=config["apikey"], base_url="https://api.deepseek.com")
        logger.logger.debug(f"向{config['model']}模型发起请求")
        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=messages,
                temperature=config["temperature"]
            )
            logger.logger.info(f"API调用成功，得到响应结果{response.choices[0].message.content}")
            
            if response.choices[0].message.reasoning_content:
                logger.logger.info(f"推理文本结果：{response.choices[0].message.reasoning_content}")
                
            logger.logger.info(f"API调用花费：{response.usage.total_tokens} tokens")
            
            return response.choices[0].message.content
        except Exception as e:
            logger.logger.error(f"API调用失败，错误信息：{str(e)}")
            return f"API Error: {str(e)}"
    
    def _process_response(self, response: str) -> List[Dict]:
        """新版响应处理流程"""
        # 步骤1：定位响应标记
        tag_match = self.response_tag_regex.search(response)
        if not tag_match:
            return []
        
        # 步骤2：提取并清理JSON内容
        json_str = tag_match.group(1).strip()
        
        # 处理常见格式问题（示例）：
        # 1. 去除末尾的无关字符
        json_str = re.sub(r'[^]]*$', '', json_str)  # 清除最后一个]后的内容
        # 2. 修复未闭合的数组
        if not json_str.endswith(']'):
            json_str += ']'
        
        # 步骤3：尝试解析JSON
        try:
            commands = json.loads(json_str)
            if not isinstance(commands, list):  # 确保是数组格式
                return []
        except json.JSONDecodeError as e:
            print(f"JSON解析错误：{str(e)}")
            return []
        
        # 步骤4：验证命令格式
        valid_commands = []
        for cmd in commands:
            if isinstance(cmd, dict) and all(key in cmd for key in ("cmd", "para", "return_method")):
                valid_commands.append({
                    "cmd": cmd["cmd"],
                    "para": cmd["para"],
                    "return_method": cmd["return_method"]
                })
        return valid_commands
     
    def _common_process(self, user_input: str, is_auto: bool = False) -> List[Dict]:
        """通用处理流程"""
        logger.logger.info(f"开始处理来自{'自动' if is_auto else '用户'}的消息：{user_input}")
        # 加载最新配置和历史
        history = self._load_history()
        
        # 添加用户消息到历史
        role = "system" if is_auto else "user"
        history.append({"role": role, "content": user_input})
        
        # 自动节约API调用
        if auto_api_usage_economizer:
            self.update_max_context(2)
        
        # 调用API
        response_content = self._call_api(history)
        
        # 处理响应内容
        commands = self._process_response(response_content)
        
        # 将AI响应添加到历史
        new_history = [{"role": role, "content": user_input},
                        {"role": "assistant", "content": response_content}]
        self._save_history(new_history)
        
        return commands
    
    def auto_message(self, message: str) -> List[Dict]:
        """自动触发消息处理"""
        logger.logger.info(f"自动触发消息处理：{message}")
        return self._common_process(message, is_auto=True)
    
    def user_message(self, message: str) -> List[Dict]:
        """处理用户输入"""
        logger.logger.info(f"用户请求消息处理：{message}")
        return self._common_process(message, is_auto=False)
    
    def cmd_message(self, message: str) -> List[Dict]:
        """处理命令输入"""
        logger.logger.info(f"AI请求命令返回信息处理：{message}")
        return self._common_process(message, is_auto=True)