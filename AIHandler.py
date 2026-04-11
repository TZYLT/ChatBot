# aihandler.py
import json
import re
import openai
import tools.CmdExecutor as CmdExecutor
import logger
from math import sqrt
from typing import List, Dict
# 导入独立配置管理器
from config_manager import ConfigManager

auto_api_usage_economizer = True  # 是否开启自动API节约算法

class aihandler:
    def __init__(self):
        # 初始化配置管理器（核心替换）
        self.config_manager = ConfigManager()
        # 新增响应标记匹配模式
        self.response_tag_regex = re.compile(
            r'<response>(.*)',
            re.DOTALL
        )
        logger.logger.info("AI处理器初始化完成")

    # ===================== 历史记录方法（无修改）=====================
    def _save_history(self, message: List[Dict]):
        """保存历史记录（不包含第一条系统提示词）"""
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
        # 直接通过配置管理器获取完整配置
        config = self.config_manager.get_all()
        try:
            with open('history.json', 'r', encoding='utf-8') as f:
                saved_dialog = json.load(f)

            new_history = [
                {"role": "system", "content": config["system_prompt"]},
                *saved_dialog
            ]

            max_ctx = config.get("now_max_context", 10)
            keep_from = max(-(max_ctx-1), -len(new_history)+1)
            final_history = [new_history[0]] + new_history[keep_from:]

            logger.logger.info(f"历史记录已加载，保留最新{max_ctx}条")
            return final_history
        except (FileNotFoundError, json.JSONDecodeError):
            logger.logger.warning("历史记录文件不存在或格式错误，创建新历史记录")
            return [{"role": "system", "content": config["system_prompt"]}]

    # ===================== 配置接口（统一调用ConfigManager，保留原有方法名）=====================
    def set_base_max_context(self, base_max_context: int):
        """设置基础最大上下文长度（兼容原有接口）"""
        self.config_manager.set("base_max_context", base_max_context)
        # 保留原有业务逻辑：默认值时同步now_max_context
        default_now_ctx = self.config_manager.DEFAULT_CONFIG["now_max_context"]
        if self.config_manager.get("now_max_context") == default_now_ctx:
            self.config_manager.set("now_max_context", base_max_context)
        logger.logger.info(f"基础最大上下文长度已设置为{base_max_context}，已保存到配置文件")

    def get_base_max_context(self):
        return self.config_manager.get("base_max_context")

    def set_now_max_context(self, now_max_context: int):
        self.config_manager.set("now_max_context", now_max_context)
        logger.logger.info(f"当前最大上下文长度已设置为{now_max_context}，已保存到配置文件")

    def get_now_max_context(self):
        return self.config_manager.get("now_max_context")

    def set_temperature(self, temperature: float):
        self.config_manager.set("temperature", temperature)
        logger.logger.info(f"AI温度已设置为{temperature}，已保存到配置文件")

    def get_temperature(self):
        return self.config_manager.get("temperature")

    def set_instant_memory(self, instant_memory: str):
        self.config_manager.set("instant_memory", instant_memory)
        logger.logger.info(f"即时记忆已更新为{instant_memory}，已保存到配置文件")

    def get_instant_memory(self):
        return self.config_manager.get("instant_memory")

    # ===================== 业务方法（无修改，仅配置读取替换）=====================
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
        config = self.config_manager.get_all()
        client = openai.OpenAI(api_key=config["apikey"], base_url="https://api.deepseek.com")
        logger.logger.debug(f"向{config['model']}模型发起请求")
        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=messages,
                temperature=config["temperature"]
            )
            message = response.choices[0].message
            content = message.content
            reasoning = getattr(message, 'reasoning_content', None)

            logger.logger.info(f"API调用成功，得到响应结果：{content}")
            if reasoning is not None:
                logger.logger.info(f"推理文本结果：{reasoning}")
            else:
                logger.logger.info("推理文本结果：无推理文本（当前模型不支持）")
            logger.logger.info(f"API调用花费：{response.usage.total_tokens} tokens")
            return content
        except Exception as e:
            logger.logger.error(f"API调用失败，错误信息：{str(e)}")
            return f"API Error: {str(e)}"

    def _process_response(self, response: str) -> List[Dict]:
        """新版响应处理流程"""
        tag_match = self.response_tag_regex.search(response)
        if not tag_match:
            return []

        json_str = tag_match.group(1).strip()
        json_str = re.sub(r'[^]]*$', '', json_str)
        if not json_str.endswith(']'):
            json_str += ']'

        try:
            commands = json.loads(json_str)
            if not isinstance(commands, list):
                return []
        except json.JSONDecodeError as e:
            print(f"JSON解析错误：{str(e)}")
            return []

        valid_commands = []
        for cmd in commands:
            if isinstance(cmd, dict) and "cmd" in cmd and "para" in cmd:
                valid_commands.append({
                    "cmd": cmd["cmd"],
                    "para": cmd["para"]
                })
        return valid_commands

    def _common_process(self, user_input: str, is_auto: bool = False) -> List[Dict]:
        """通用处理流程"""
        logger.logger.info(f"开始处理来自{'自动' if is_auto else '用户'}的消息：{user_input}")
        history = self._load_history()

        role = "user"
        history.append({"role": role, "content": f"{user_input}[MEMORY:{self.get_instant_memory()}]"})

        if auto_api_usage_economizer:
            self.update_max_context(2)

        response_content = self._call_api(history)
        commands = self._process_response(response_content)

        new_history = [
            {"role": role, "content": user_input},
            {"role": "assistant", "content": response_content}
        ]
        self._save_history(new_history)

        return commands

    def auto_message(self, message: str) -> List[Dict]:
        logger.logger.info(f"自动触发消息处理：{message}")
        return self._common_process(message, is_auto=True)

    def user_message(self, message: str) -> List[Dict]:
        logger.logger.info(f"用户请求消息处理：{message}")
        return self._common_process(message, is_auto=False)

    def cmd_message(self, message: str) -> List[Dict]:
        logger.logger.info(f"AI请求命令返回信息处理：{message}")
        return self._common_process(message, is_auto=True)