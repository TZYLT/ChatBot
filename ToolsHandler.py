import json
import threading
import queue
import uuid
import os
import importlib.util
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
import logger

class ToolInvoker:
    def __init__(self, plugin_dir: str = "./tools"):
        # 核心任务调度组件（保留原有逻辑）
        self.task_queue = queue.Queue()
        self.tasks = {}
        self.lock = threading.Lock()
        self._start_worker()

        # ===================== 插件化改造核心 =====================
        # 工具注册表：key=工具名，value={完整元信息 + 执行函数}
        self.tool_registry: Dict[str, Dict[str, Any]] = {}
        # 自动扫描并加载 tools 目录下所有插件（递归遍历）
        self._auto_load_plugins(plugin_dir)

    # ===================== 对外开放的注册接口（插件调用） =====================
    def register_tool(
        self,
        name: str,
        summary: str,
        description: str,
        para_desc: str,
        warning: str,
        func: Callable[..., str]
    ):
        """
        插件统一调用此方法注册工具
        :param name: 工具唯一名称
        :param summary: 工具简介
        :param description: 工具详细描述
        :param para_desc: 参数描述 {参数名: 说明}
        :param warning: 使用警告/注意事项
        :param func: 工具执行函数/方法
        """
        self.tool_registry[name] = {
            "name": name,
            "summary": summary,
            "description": description,
            "para_desc": para_desc,
            "warning": warning,
            "func": func
        }

    # ===================== 递归扫描所有子目录 + 动态导入 =====================
    def _auto_load_plugins(self, plugin_dir: str):
        """递归扫描 tools 文件夹及其所有子文件夹，加载包含 register 函数的 py 文件"""
        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir)
            logger.logger.info(f"创建插件目录: {plugin_dir}")
            return

        # 递归遍历所有子目录
        for root, dirs, files in os.walk(plugin_dir):
            for filename in files:
                # 只加载 .py 文件，跳过 __ 开头的系统文件
                if not filename.endswith(".py") or filename.startswith("__"):
                    continue

                file_path = os.path.join(root, filename)
                # 构建标准模块名：支持子目录，如 tools.subdir.module
                rel_path = os.path.relpath(file_path, plugin_dir)
                module_rel = os.path.splitext(rel_path)[0].replace(os.sep, ".")
                module_name = f"tools.{module_rel}"

                try:
                    # 动态导入模块
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 调用插件的注册函数
                    if hasattr(module, "register"):
                        module.register(self)
                        logger.logger.info(f"成功加载插件: {file_path}")
                except Exception as e:
                    logger.logger.error(f"加载插件失败 {file_path}: {str(e)}")

    # ===================== 重写：从注册表获取工具信息 =====================
    def get_tool_list(self) -> List[Dict[str, str]]:
        """获取工具列表（name+summary）"""
        return [
            {"name": info["name"], "summary": info["summary"]}
            for info in self.tool_registry.values()
        ]

    def get_tool_usage(self, name: str) -> Dict[str, Any]:
        """获取工具完整使用信息（注册时传入的所有元数据）"""
        return self.tool_registry.get(name, {})

    # ===================== 保留原有任务管理逻辑（无修改） =====================
    def add_tasks(self, tasks: List[Dict[str, Any]]):
        """添加任务到队列"""
        for task in tasks:
            task_id = str(uuid.uuid4())
            with self.lock:
                self.tasks[task_id] = {
                    "task": task,
                    "status": "pending",
                    "response": None,
                    "returned": False
                }
            self.task_queue.put({"id": task_id, "task": task})

    def get_responses(self) -> List[Dict[str, str]]:
        """获取任务结果（自动清理已完成任务）"""
        results = []
        tasks_to_remove = []
        with self.lock:
            for task_id, task_info in list(self.tasks.items()):
                if task_info["status"] == "completed":
                    if not task_info["returned"]:
                        results.append({
                            "name": task_info["task"]["name"],
                            "response": task_info["response"]
                        })
                        task_info["returned"] = True
                    else:
                        tasks_to_remove.append(task_id)
                else:
                    results.append({
                        "name": task_info["task"]["name"],
                        "response": "Waiting for responses."
                    })
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
        return results

    # ===================== 重写：查表执行工具，无硬编码 =====================
    def _call_tool(self, name: str, para: Dict[str, Any]) -> str:
        """统一工具调用（从注册表查表执行）"""
        try:
            tool_info = self.tool_registry.get(name)
            if not tool_info:
                return f"错误: 未知工具 '{name}'"

            # 执行注册的工具函数
            return tool_info["func"](**para)
        except Exception as e:
            return f"工具执行错误: {str(e)}"

    # ===================== 保留原有工作线程逻辑（无修改） =====================
    def _worker(self):
        """后台工作线程，处理任务队列"""
        while True:
            try:
                item = self.task_queue.get(timeout=1)
                task_id = item["id"]
                task = item["task"]
                name = task.get("name")
                para = task.get("para", {})

                # 更新状态：执行中
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]["status"] = "processing"

                # 执行工具
                response = self._call_tool(name, para)

                # 更新状态：已完成
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]["status"] = "completed"
                        self.tasks[task_id]["response"] = response

                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                with self.lock:
                    if task_id in self.tasks:
                        self.tasks[task_id]["status"] = "completed"
                        self.tasks[task_id]["response"] = f"工具调用出错: {str(e)}"
                self.task_queue.task_done()

    def _start_worker(self):
        """启动后台线程"""
        worker_thread = threading.Thread(target=self._worker, daemon=True)
        worker_thread.start()