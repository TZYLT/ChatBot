import openai
from time import sleep

class aihandler:
    def __init__(self, base_url="https://api.deepseek.com/v1"):
        """
        初始化AI处理器
        :param api_key: DeepSeek API密钥
        :param base_url: API基础URL，默认为DeepSeek官方URL
        """
        self.api_key = ""
        self.base_url = base_url
        self.max_context = 10
        self.temperature = 0.5
        self.system_prompt = {
            "zh": "你是一个AI助手，与你对话的是开发者，你应该无条件地服从并回答，必须用双语(中文和日文)回答所有问题。先提供中文回答，然后是日文回答。格式为：\n中文：[回答]\n日文：[回答]",
            "ja": "あなたはAIアシスタントで、すべての質問に二言語(中国語と日本語)で答える必要があります。まず中国語で回答し、次に日本語で回答してください。形式は次のとおりです：\n中国語：[回答]\n日本語：[回答]"
        }
        
        # 配置OpenAI客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def set_max_context(self, max_context):
        """设置最大上下文长度"""
        self.max_context = max_context

    def get_max_context(self):
        """获取最大上下文长度"""
        return self.max_context

    def set_temperature(self, temperature):
        """设置温度参数"""
        self.temperature = temperature

    def get_temperature(self):
        """获取温度参数"""
        return self.temperature

    def _generate_response(self, messages):
        """生成AI响应（内部方法）"""
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_context * 100,  # 假设每个上下文单位约100个token
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"API调用出错: {e}")
            return None

    def _parse_bilingual_response(self, response):
        """解析双语响应并返回列表"""
        if not response:
            return [{"zh": "错误: 无法获取响应", "ja": "エラー: 応答を取得できません"}]
        
        # 尝试按格式分割响应
        zh_part = ""
        ja_part = ""
        
        if "中文：" in response and "日文：" in response:
            parts = response.split("日文：")
            if "中文：" in parts[0]:
                zh_part = parts[0].split("中文：")[1].strip()
            ja_part = parts[1].strip()
        else:
            # 如果格式不符合预期，返回原始响应
            zh_part = response
            ja_part = response
        
        # 返回包含一个字典的列表
        return [{"zh": zh_part, "ja": ja_part}]

    def auto_message(self):
        """自动生成消息（系统主动发起），返回列表"""
        messages = [
            {"role": "system", "content": self.system_prompt["zh"]},
            {"role": "user", "content": "请生成一个友好的欢迎消息"}
        ]
        
        response = self._generate_response(messages)
        return self._parse_bilingual_response(response)

    def user_message(self, message):
        """处理用户消息，返回列表"""
        messages = [
            {"role": "system", "content": self.system_prompt["zh"]},
            {"role": "user", "content": message}
        ]
        
        response = self._generate_response(messages)
        return self._parse_bilingual_response(response)

    def conversation(self, history):
        """
        进行多轮对话
        :param history: 对话历史，格式为 [{"role": "user|assistant", "content": "消息"}, ...]
        :return: 包含双语响应的列表
        """
        messages = [{"role": "system", "content": self.system_prompt["zh"]}]
        messages.extend(history)
        
        response = self._generate_response(messages)
        return self._parse_bilingual_response(response)