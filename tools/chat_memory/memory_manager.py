import os
from datetime import datetime
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, DATETIME, NUMERIC, ID
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh.analysis import Tokenizer, Token
from pathlib import Path
import sys
import jieba
from typing import List, Dict, Optional
import json

parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)
import logger

class JiebaTokenizer(Tokenizer):
    """自定义Jieba分词器用于Whoosh"""
    def __call__(self, value, positions=False, chars=False,
                 keeporiginal=False, removestops=True,
                 start_pos=0, start_char=0, mode='', **kwargs):
        words = jieba.cut_for_search(value)
        token = Token(positions, chars, removestops=removestops, mode=mode,
                      **kwargs)
        for w in words:
            token.original = token.text = w
            token.boost = 1.0
            if positions:
                token.pos = start_pos + value.find(w)
            if chars:
                token.startchar = start_char + value.find(w)
                token.endchar = start_char + value.find(w) + len(w)
            yield token

class MemorySearchEngine:
    """记忆搜索引擎封装类"""
    def __init__(self, index_dir: str = "memory"):
        """
        初始化搜索引擎
        :param index_dir: 索引目录路径（相对于当前目录）
        """
        logger.logger.debug("开始初始化记忆搜索引擎")
        # 获取当前脚本所在目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建完整的索引目录路径
        self.index_dir = os.path.join(current_dir, index_dir)
        
        self.schema = Schema(
            memory_id=ID(stored=True, unique=True),  # 记忆唯一ID
            content=TEXT(analyzer=JiebaTokenizer(), stored=True),  # 记忆内容
            keywords=TEXT(analyzer=JiebaTokenizer(), stored=True),  # 关键词
            time=DATETIME(stored=True),  # 记忆时间
            extract_count=NUMERIC(float, stored=True),  # 提取次数
            memory_stability=NUMERIC(float, stored=True),  # 记忆稳定性
            memory_growth=NUMERIC(float, stored=True),  # 记忆增长度
            memory_adjustment=NUMERIC(float, stored=True),  # 记忆修正量
        )
        
        # 确保索引目录存在
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)
        
        # 创建或打开索引
        if exists_in(self.index_dir):
            self.ix = open_dir(self.index_dir)
        else:
            self.ix = create_in(self.index_dir, self.schema)
        logger.logger.info("记忆搜索引擎初始化完成")
    
    def add_memory(self, memory_id: str, content: str, time: datetime, 
                  keywords: List[str], extract_count: float, 
                  memory_stability: float, memory_growth: float, 
                  memory_adjustment: float) -> None:
        """
        添加或更新记忆
        :param memory_id: 记忆唯一ID
        :param content: 记忆内容
        :param time: 记忆时间
        :param keywords: 关键词列表
        :param extract_count: 提取次数
        :param memory_stability: 记忆稳定性
        :param memory_growth: 记忆增长度
        :param memory_adjustment: 记忆修正量
        """
        writer = self.ix.writer()
        
        # 先尝试删除已存在的记录（如果存在）
        writer.delete_by_term('memory_id', memory_id)
        
        # 添加新记录
        writer.add_document(
            memory_id=memory_id,
            content=content,
            keywords=" ".join(keywords),
            time=time,
            extract_count=extract_count,
            memory_stability=memory_stability,
            memory_growth=memory_growth,
            memory_adjustment=memory_adjustment
        )
        
        writer.commit()
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除指定记忆
        :param memory_id: 要删除的记忆ID
        :return: 是否成功删除
        """
        writer = self.ix.writer()
        count = writer.delete_by_term('memory_id', memory_id)
        writer.commit()
        return count > 0
    
    def search(self, query_str: str = "", keyword_str: str = "", 
              start_time: Optional[datetime] = None, 
              end_time: Optional[datetime] = None,
              limit: int = 10) -> List[Dict]:
        """
        搜索记忆
        :param query_str: 搜索的句子
        :param keyword_str: 搜索的关键词
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param limit: 返回结果数量限制
        :return: 搜索结果列表，每个结果是一个字典
        """
        results = []
        with self.ix.searcher() as searcher:
            # 构建查询条件
            conditions = []
            
            if query_str:
                query_parser = QueryParser("content", self.ix.schema)
                query = query_parser.parse(query_str)
                conditions.append(query)
            
            if keyword_str:
                keyword_parser = QueryParser("keywords", self.ix.schema)
                keyword_query = keyword_parser.parse(keyword_str)
                conditions.append(keyword_query)
            
            # 组合查询条件
            if len(conditions) > 1:
                from whoosh.query import And
                combined_query = And(conditions)
            elif conditions:
                combined_query = conditions[0]
            else:
                combined_query = None
            
            # 时间范围过滤
            if start_time or end_time:
                from whoosh.query import TermRange
                time_query = TermRange("time", start_time, end_time)
                if combined_query:
                    from whoosh.query import And
                    combined_query = And([combined_query, time_query])
                else:
                    combined_query = time_query
            
            # 如果没有查询条件，返回空列表
            if not combined_query:
                return results
            
            # 执行搜索
            hits = searcher.search(combined_query, limit=limit)
            
            for hit in hits:
                results.append({
                    'memory_id': hit['memory_id'],
                    'content': hit['content'],
                    'keywords': hit['keywords'].split(),
                    'time': hit['time'],
                    'extract_count': hit['extract_count'],
                    'memory_stability': hit['memory_stability'],
                    'memory_growth': hit['memory_growth'],
                    'memory_adjustment': hit['memory_adjustment'],
                    'score': hit.score
                })
        logger.logger.info(f"对于'{query_str}'的搜索，'{keyword_str}'的关键词，时间范围为{start_time}到{end_time}，找到{len(results)}条搜索结果")
        return results
    
    def search_by_fields(self, query_str: str, fields: List[str] = None, 
                        limit: int = 10) -> List[Dict]:
        """
        在多个字段中搜索
        :param query_str: 搜索字符串
        :param fields: 要搜索的字段列表，默认为['content', 'keywords']
        :param limit: 返回结果数量限制
        :return: 搜索结果列表
        """
        if fields is None:
            fields = ['content', 'keywords']
        
        results = []
        with self.ix.searcher() as searcher:
            parser = MultifieldParser(fields, self.ix.schema)
            query = parser.parse(query_str)
            hits = searcher.search(query, limit=limit)
            
            for hit in hits:
                results.append({
                    'memory_id': hit['memory_id'],
                    'content': hit['content'],
                    'keywords': hit['keywords'].split(),
                    'time': hit['time'],
                    'extract_count': hit['extract_count'],
                    'memory_stability': hit['memory_stability'],
                    'memory_growth': hit['memory_growth'],
                    'memory_adjustment': hit['memory_adjustment'],
                    'score': hit.score
                })
        
        return results
    
    def clear_index(self) -> None:
        """清空所有索引"""
        writer = self.ix.writer()
        writer.delete_by_query(QueryParser("memory_id", self.schema).parse("*"))
        writer.commit()
    
    def get_all_memories(self) -> List[Dict]:
        """获取所有记忆"""
        return self.search_by_fields("*")
    

    def export_to_json(self, file_path: str = None) -> Optional[str]:
        """
        将所有记忆导出为JSON格式
        
        :param file_path: 要保存的JSON文件路径，如果为None则返回JSON字符串
        :return: 如果file_path为None则返回JSON字符串，否则返回None
        """
        logger.logger.info(f"导出所有记忆到JSON文件{file_path}")
        # 获取所有记忆
        memories = self.get_all_memories()
        
        # 准备导出数据（将datetime对象转换为字符串）
        export_data = []
        for mem in memories:
            mem_copy = mem.copy()
            # 将datetime对象转为ISO格式字符串
            if isinstance(mem_copy['time'], datetime):
                mem_copy['time'] = mem_copy['time'].isoformat()
            export_data.append(mem_copy)
        
        # 如果指定了文件路径，则写入文件
        if file_path is not None:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            return None
        else:
            # 返回JSON字符串
            return json.dumps(export_data, ensure_ascii=False, indent=2)