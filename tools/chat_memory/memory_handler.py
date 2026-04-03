import os
import json
import random
import math
import copy
from datetime import datetime
from typing import List, Dict, Optional
from .memory_manager import MemorySearchEngine
import sys
from pathlib import Path

parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)
import logger

class MemoryHandler:
    """记忆处理器，封装记忆的添加和查询功能"""
    def __init__(self, config_file: str = "memory_config.json"):
        """
        初始化记忆处理器
        :param config_file: 配置文件路径（相对于当前目录）
        """
        # 获取当前脚本所在目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(current_dir, config_file)
        
        # 初始化搜索引擎
        self.engine = MemorySearchEngine()
        
        # 加载或初始化配置
        self.config = self._load_config()
        
        # 初始化记忆ID计数器
        self.s_base = self.config["settings"]["s_base"]      # 基础稳定性
        self.alpha = self.config["settings"]["alpha"]          # 稳定性衰减系数
        self.c_base = self.config["settings"]["c_base"]      # 基础增长系数
        self.beta = self.config["settings"]["beta"]            # 长度增益系数

        self.current_id = self.config.get("last_id", 0)
        logger.logger.info("记忆处理器初始化完成")

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                logger.logger.info("记忆处理器加载配置文件成功")
                return json.load(f)
        logger.logger.warning("记忆处理器加载配置文件失败，使用默认配置")
        return {
            "last_id": 0,
            "settings": {
                "s_base": 10.0,
                "alpha": 0.06,
                "c_base": 1.15,
                "beta": 0.05,
            }
        }
    
    def _save_config(self) -> None:
        """保存配置文件"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.logger.info("记忆处理器保存配置文件成功")
    
    def generate_memory_parameters(self, length):
        """
        根据信息长度生成初始记忆稳定性 (s) 和增长系数 (c)
        参数:length (int): 信息的字符长度 (len >= 1)
        返回:tuple (s, c): 初始稳定性 s (float), 增长系数 c (float)
        """
        
        # s = s_base / (1 + alpha*length) * (1 ± 10% 扰动)
        epsilon_s = random.uniform(-0.1, 0.1)  # 均匀扰动 ±10%
        s = (self.s_base / (1 + self.alpha * length)) * (1 + epsilon_s)
        
        # c = c_base + beta*ln(length+1) + 正态扰动 (μ=0, σ=0.01)
        epsilon_c = random.normalvariate(0, 0.02)  # 正态分布扰动
        c = self.c_base + self.beta * math.log(length + 1) + epsilon_c
        c = max(c, 1.01)  # 强制 c > 1 避免数学错误
    
        return round(s, 2), round(c, 4)  # 保留小数位
    
    def add_memory(self, content: str, keywords: List[str], time: Optional[datetime] = None):
        """
        添加记忆（自动生成四种数值）
        :param content: 记忆内容
        :param keywords: 关键词列表
        :param time: 记忆时间，默认为当前时间
        :return: 生成的记忆ID
        """
        # 生成新ID
        self.current_id += 1
        memory_id = str(self.current_id)
        
        # 更新时间
        if time is None:
            time = datetime.now()
        
        # 生成随机数值
        s, c = self.generate_memory_parameters(len(content))
        extract_count = 0.0
        memory_stability = s
        memory_growth = c
        memory_adjustment = 0.0
        
        # 添加记忆
        self.engine.add_memory(
            memory_id=memory_id,
            content=content,
            time=time,
            keywords=keywords,
            extract_count=extract_count,
            memory_stability=memory_stability,
            memory_growth=memory_growth,
            memory_adjustment=memory_adjustment
        )
        
        # 更新配置
        self.config["last_id"] = self.current_id
        self._save_config()
        
        logger.logger.info(f"添加记忆\"{content}\"成功，关键词：{keywords}，ID：{memory_id}")
        # return memory_id
    
    def read_memories(self, query_str: str = "", keyword_str: str = "", 
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     limit: Optional[int] = None) -> List[Dict]:
        """
        读取记忆
        :param query_str: 搜索的句子
        :param keyword_str: 搜索的关键词
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param limit: 返回结果数量限制，默认为配置中的默认值
        :return: 搜索结果列表
        """
        if limit is None:
            limit = self.config["settings"].get("default_limit", 10)

        memories_response = self.engine.search(
                                query_str=query_str,
                                keyword_str=keyword_str,
                                start_time=start_time,
                                end_time=end_time,
                                limit=limit
                            )
        
        # 处理记忆内容
        memories_actual = copy.deepcopy(memories_response)
        for i in range(len(memories_actual)):
            memories_actual[i]["content"] = self.process_memory_string(
                        s=memories_actual[i]["memory_stability"],
                        c=memories_actual[i]["memory_growth"],
                        k=memories_actual[i]["extract_count"],
                        saved_time=memories_actual[i]["time"],
                        info_str=memories_actual[i]["content"]
                    )
            # 更新记忆数值
            memories_response[i]["extract_count"] += 1
            memories_response[i]["time"] = datetime.now()
            memories_response[i].pop("score")
            self.engine.add_memory(**memories_response[i])
        
        logger.logger.info(f"对于'{query_str}'的搜索，'{keyword_str}'的关键词，时间范围为{start_time}到{end_time}，找到{len(memories_actual)}条搜索结果")
        return memories_actual
    
    def read_all_memories(self) -> List[Dict]:
        """读取所有记忆"""
        return self.engine.get_all_memories()
    
    def process_memory_string(self,s: float, c: float, k: float, saved_time: datetime, info_str: str) -> str:
        """
        根据记忆模型处理字符串，每个字符按回忆概率保留或被替换
        Args:
            s: 记忆稳定性（s > 0）
            c: 记忆增长系数（c > 1）
            k: 回忆次数（k >= 0）
            saved_time: 记忆保存的时间（datetime对象）
            info_str: 原始信息字符串
        Returns:str: 处理后包含保留字符和下划线的字符串
        """
        # 计算时间差（小时）
        current_time = datetime.now()
        delta = current_time - saved_time
        t_hours = max(delta.total_seconds() / 86400, 0)  # 确保非负
        
        # 计算回忆概率
        denominator = s * (c ** k)
        recall_prob = math.exp(-t_hours / denominator) if denominator != 0 else 0
        
        #recall_prob = 0.8
        # 处理每个字符
        processed = []
        for char in info_str:
            if random.random() <= recall_prob:
                processed.append(char)
            else:
                processed.append('_')  # 用下划线表示遗忘
        
        return ''.join(processed)

    def clear_all(self) -> None:
        """清空所有记忆和重置计数器"""
        self.engine.clear_index()
        self.current_id = 0
        self.config["last_id"] = 0
        self._save_config()

# ===================== register 注册函数 =====================
def register(invoker):
    """
    记忆工具注册：
    包含 add_memory + read_memory
    """
    memoryHandler = MemoryHandler()

    # -------------------- 1. 注册：add_memory --------------------
    invoker.register_tool(
        name="add_memory",
        summary="向数据库写入一条记忆信息，可附加关键词",
        description="保存内容到记忆库，并传入关键词便于未来搜索",
        para_desc={
            "content": "要保存的记忆内容",
            "keywords": "关键词列表，如 ['工作', '日记']"
        },
        warning="关键词必须是列表格式，content 不能为空",
        func=memoryHandler.add_memory
    )

    # -------------------- 2. 注册：read_memory --------------------
    invoker.register_tool(
        name="read_memory",
        summary="按条件查询记忆库中的记录",
        description="可通过内容、关键词、时间范围、数量限制来精确查询记忆",
        para_desc={
            "query_str": "要精确匹配的内容（可选）",
            "keyword_str": "单个关键词字符串（可选）",
            "start_time": "开始时间 %Y-%m-%dT%H:%M:%S（可选）",
            "end_time": "结束时间 %Y-%m-%dT%H:%M:%S（可选）",
            "limit": "返回最大条数，默认10（可选）"
        },
        warning="查询不支持模糊搜索，必须输入准确字符串；时间格式必须严格匹配",
        func=memoryHandler.read_memories
    )