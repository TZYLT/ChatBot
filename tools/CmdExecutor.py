import subprocess
import tkinter as tk
from tkinter import simpledialog

import sys
from pathlib import Path

# 获取上一级目录的绝对路径
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)
import logger

def request_command_approval(command: str) -> str:
    """
    弹出授权窗口，让用户选择是否允许执行命令。
    返回用户的选择（批准/驳回/驳回并附理由）。
    """
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    # 创建自定义弹窗
    approval_window = tk.Toplevel(root)
    approval_window.title("Command Execution Approval")
    
    # 设置窗口大小和位置
    approval_window.geometry("400x200")
    approval_window.resizable(True, True)
    
    # 显示命令内容
    tk.Label(
        approval_window,
        text=f"The following command will be executed:",
        font=("Arial", 10),
    ).pack(pady=5)
    
    tk.Label(
        approval_window,
        text=f"`{command}`",
        wraplength=350,
        justify="left",
        font=("Courier", 10),
        fg="blue",
    ).pack(pady=5)
    
    tk.Label(
        approval_window,
        text="Do you want to allow this command?",
        font=("Arial", 10),
    ).pack(pady=10)
    
    # 存储用户的选择
    user_choice = {"status": None, "reason": None}
    
    def approve():
        user_choice["status"] = "approved"
        approval_window.destroy()
    
    def reject():
        user_choice["status"] = "rejected"
        approval_window.destroy()
    
    def reject_with_reason():
        reason = simpledialog.askstring(
            "Rejection Reason",
            "Please enter the reason for rejection:",
            parent=approval_window,
        )
        if reason:  # 用户输入了理由
            user_choice["status"] = "rejected_with_reason"
            user_choice["reason"] = reason
        else:  # 用户未输入理由，默认驳回
            user_choice["status"] = "rejected"
        approval_window.destroy()
    
    # 批准、驳回、驳回并输入理由 三个按钮
    tk.Button(
        approval_window,
        text="✅ Approve",
        command=approve,
        bg="green",
        fg="white",
    ).pack(side=tk.LEFT, padx=10, pady=10)
    
    tk.Button(
        approval_window,
        text="📝 Reject with Reason",
        command=reject_with_reason,
        bg="orange",
        fg="black",
    ).pack(side=tk.RIGHT, padx=10, pady=10)
    
    tk.Button(
        approval_window,
        text="❌ Reject",
        command=reject,
        bg="red",
        fg="white",
    ).pack(side=tk.RIGHT, padx=10, pady=10)
    
    # 等待用户操作
    approval_window.wait_window()
    root.destroy()
    
    return user_choice

def run_command_with_approval(command: str) -> str:
    """
    执行命令行命令，但先弹出授权窗口。
    返回执行结果或驳回信息。
    """
    logger.logger.info(f"Requesting approval for command: \"{command[0:10]}...\"")
    # 1. 请求用户授权
    approval_result = request_command_approval(command)
    
    # 2. 根据用户选择处理
    if approval_result["status"] == "approved":
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.logger.info(f"Approval result: \"Approved\"")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.logger.info(f"Approval result: \"Approved\" but command failed with error: {e.stderr}")
            return f"Command failed with error: {e.stderr}"
    
    elif approval_result["status"] == "rejected":
        logger.logger.info(f"Approval result: \"Rejected\"")
        return "Command rejected by user."
    
    elif approval_result["status"] == "rejected_with_reason":
        logger.logger.info(f"Approval result: \"Rejected\" with reason: {approval_result['reason']}")
        return f"Command rejected. Reason: {approval_result['reason']}"
    
    else:
        logger.logger.info(f"Approval result: Cancelled")
        return "Command execution cancelled."