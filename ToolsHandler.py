import json
import threading
import queue
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

### 导入工具模块
import tools.CmdExecutor as CmdExecutor
import tools.TextReader as TextReader
from chat_memory.memory_handler import MemoryHandler
###

class ToolInvoker:
    def __init__(self, config_path: str = "./tools/config.json"):
        self.config_path = config_path
        self.tools_config = self._load_config()
        self.task_queue = queue.Queue()
        self.tasks = {}  # 使用字典存储所有任务，键为任务ID，值为任务信息和状态
        self.lock = threading.Lock()
        self.memory_handler = MemoryHandler()  # 记忆处理器
        self._start_worker()
        
        self.textReader = TextReader.DocumentProcessor()
    
    def _load_config(self) -> List[Dict[str, Any]]:
        """加载工具配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: 配置文件 {self.config_path} 未找到")
            return []
        except json.JSONDecodeError:
            print(f"错误: 配置文件 {self.config_path} 格式错误")
            return []
    
    def get_tool_list(self) -> List[Dict[str, str]]:
        """获取工具列表，包含name和summary字段"""
        tool_list = []
        for tool in self.tools_config:
            tool_list.append({
                'name': tool.get('name', ''),
                'summary': tool.get('summary', '')
            })
        return tool_list
    
    def get_tool_usage(self, name: str) -> Dict[str, Any]:
        """获取指定工具的完整使用信息"""
        for tool in self.tools_config:
            if tool.get('name') == name:
                return tool
        return {}
    
    def add_tasks(self, tasks: List[Dict[str, Any]]):
        """添加任务到队列"""
        for task in tasks:
            task_id = str(uuid.uuid4())  # 为每个任务生成唯一ID
            with self.lock:
                self.tasks[task_id] = {
                    'task': task,
                    'status': 'pending',  # 任务状态: pending, processing, completed
                    'response': None,
                    'returned': False  # 标记是否已经返回过结果
                }
            # 将任务ID与任务一起放入队列
            self.task_queue.put({'id': task_id, 'task': task})
    
    def get_responses(self) -> List[Dict[str, str]]:
        """获取所有任务的状态，已完成的任务只返回一次"""
        results = []
        tasks_to_remove = []
        
        with self.lock:
            for task_id, task_info in list(self.tasks.items()):
                if task_info['status'] == 'completed':
                    if not task_info['returned']:
                        # 已完成但尚未返回的任务，返回结果并标记为已返回
                        results.append({
                            'name': task_info['task']['name'],
                            'response': task_info['response']
                        })
                        task_info['returned'] = True
                    else:
                        # 已完成且已返回的任务，标记为待删除
                        tasks_to_remove.append(task_id)
                else:
                    # 未完成的任务，返回等待消息
                    results.append({
                        'name': task_info['task']['name'],
                        'response': "Waiting for responses."
                    })
            
            # 删除已完成且已返回的任务
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
        
        return results
    
    def _call_tool(self, name: str, para: Dict[str, Any]) -> str:
        """统一工具调用函数"""
        try:
            # 这里根据工具名称调用不同的工具
            if name == "CmdExecutor":
                return CmdExecutor.run_command_with_approval(**para)
            elif name == "GetToolsList":
                return str(self.get_tool_list())
            elif name == "GetToolUsage":
                return str(self.get_tool_usage(para.get('name', '')))
            elif name == "count_text_lines":
                return str(self.textReader.count_text_lines(**para))
            elif name == "get_text_lines":
                return str(self.textReader.get_text_lines(**para))
            elif name == "add_text_line":
                return str(self.textReader.add_text_line(**para))
            elif name == "add_memory":
                # 添加记忆
                self.memory_handler.add_memory(**para)
                return "记忆添加成功"
            elif name == "read_memories":
                # 读取记忆
                para["start_time"] = datetime.strptime(para["start_time"], "%Y-%m-%dT%H:%M:%S")
                para["end_time"] = datetime.strptime(para["end_time"], "%Y-%m-%dT%H:%M:%S")
                return_memories = self.memory_handler.read_memories(**para)
                return f"读取到的记忆：{return_memories}"
            # 添加更多工具的调用...
            else:
                return f"错误: 未知工具 '{name}'"
        except Exception as e:
            return f"工具执行错误: {str(e)}"
    
    def _worker(self):
        """工作线程函数，处理任务队列"""
        while True:
            try:
                item = self.task_queue.get(timeout=1)
                task_id = item['id']
                task = item['task']
                name = task.get('name')
                para = task.get('para', {})
                
                # 更新任务状态为处理中
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]['status'] = 'processing'
                
                # 调用工具
                response = self._call_tool(name, para)
                
                # 更新任务状态和结果
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]['status'] = 'completed'
                        self.tasks[task_id]['response'] = response
                
                self.task_queue.task_done()
            except queue.Empty:
                # 队列为空时继续等待
                continue
            except Exception as e:
                # 处理异常
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]['status'] = 'completed'
                        self.tasks[task_id]['response'] = f"工具调用出错: {str(e)}"
                self.task_queue.task_done()
    
    def _start_worker(self):
        """启动工作线程"""
        worker_thread = threading.Thread(target=self._worker, daemon=True)
        worker_thread.start()