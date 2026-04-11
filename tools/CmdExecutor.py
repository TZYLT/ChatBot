import subprocess
import tkinter as tk
from tkinter import simpledialog

import sys
import re
from pathlib import Path

# 获取上一级目录的绝对路径
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)
import logger


def is_sensitive_command(command: str) -> bool:
    """
    检测命令是否敏感（可能破坏系统或数据）
    返回 True 表示需要用户确认，False 表示可以自动执行
    """
    # 敏感命令列表（小写）
    sensitive_commands = [
        'del', 'erase', 'rm', 'rmdir', 'rd',          # 删除文件/目录
        'format',                                      # 格式化磁盘
        'diskpart',                                    # 磁盘分区工具
        'reg',                                         # 注册表操作（增删改）
        'shutdown', 'reboot',                          # 关机/重启
        'taskkill',                                    # 强制终止进程
        'cacls', 'icacls', 'takeown',                  # 修改文件权限/所有权
        'sc',                                          # 服务控制（创建/删除/启动/停止）
        'bcdedit',                                     # 启动配置数据编辑
        'vssadmin',                                    # 卷影复制管理（可能删除备份）
        'wmic',                                        # 危险操作如删除进程/文件
        'powershell',                                  # 执行复杂脚本，风险较高
        'net',                                         # 用户/组/共享等修改（如 net user /add）
    ]

    command_lower = command.lower()
    # 处理多命令串联：分割 &&, ||, &, |, ; 等
    delimiters = r'&&|\|\||&|\||;'
    sub_commands = re.split(delimiters, command_lower)

    for sub_cmd in sub_commands:
        sub_cmd = sub_cmd.strip()
        if not sub_cmd:
            continue
        # 获取命令名（第一个词）
        parts = sub_cmd.split()
        if not parts:
            continue
        cmd_name = parts[0]
        # 去除可能的路径前缀（如 C:\Windows\System32\cmd.exe -> cmd）
        cmd_base = Path(cmd_name).stem

        # 检查命令名是否在敏感列表中
        if cmd_base in sensitive_commands:
            return True

        # 额外用单词边界检测，避免漏掉如 "del file.txt" 中 del 被路径前缀掩盖的情况
        for sens_cmd in sensitive_commands:
            if re.search(r'\b' + re.escape(sens_cmd) + r'\b', sub_cmd):
                return True

    return False


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
    执行命令行命令，自动检测敏感操作：
    - 不敏感命令：直接执行，无需用户确认
    - 敏感命令：弹出授权窗口等待用户批准
    返回执行结果或驳回信息。
    """
    logger.logger.info(f"Checking command: \"{command[:50]}{'...' if len(command) > 50 else ''}\"")

    # 自动检测敏感命令
    if not is_sensitive_command(command):
        logger.logger.info(f"Auto-approved non-sensitive command: \"{command}\"")
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',      # 强制使用 UTF-8 解码，避免 Windows 默认 GBK 报错
                errors='replace'       # 遇到无法解码的字节替换为 �
            )
            logger.logger.info(f"Command executed successfully (auto-approved)")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.logger.error(f"Auto-approved command failed: {e.stderr}")
            return f"Command failed with error: {e.stderr}"
        except Exception as e:
            logger.logger.error(f"Unexpected error while executing auto-approved command: {e}")
            return f"Execution error: {e}"
    else:
        # 敏感命令，请求用户确认
        logger.logger.info(f"Sensitive command detected, requesting approval: \"{command}\"")
        approval_result = request_command_approval(command)

        if approval_result["status"] == "approved":
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                logger.logger.info(f"Approval result: \"Approved\"")
                return result.stdout
            except subprocess.CalledProcessError as e:
                logger.logger.info(f"Approval result: \"Approved\" but command failed with error: {e.stderr}")
                return f"Command failed with error: {e.stderr}"
            except Exception as e:
                logger.logger.error(f"Unexpected error: {e}")
                return f"Execution error: {e}"

        elif approval_result["status"] == "rejected":
            logger.logger.info(f"Approval result: \"Rejected\"")
            return "Command rejected by user."

        elif approval_result["status"] == "rejected_with_reason":
            logger.logger.info(f"Approval result: \"Rejected\" with reason: {approval_result['reason']}")
            return f"Command rejected. Reason: {approval_result['reason']}"

        else:
            logger.logger.info(f"Approval result: Cancelled")
            return "Command execution cancelled."


def register(invoker):
    """
    插件注册入口，将自动被 ToolInvoker 扫描并调用
    """
    invoker.register_tool(
        name="CmdExecutor",
        summary="执行CMD命令（自动检测敏感操作）",
        description="通过命令提示符执行cmd命令。自动检测敏感操作（如删除、格式化、修改注册表等），不敏感的命令直接执行，敏感命令会弹出窗口请求用户确认，因此无需担心安全性。",
        para_desc="\"command\":str - 传入你想要执行的命令，一个字符串。",
        warning="你不应该使用可能产生过量输出的命令，例如进行目录树递归操作。",
        func=run_command_with_approval  # 绑定工具执行函数
    )

if __name__ == '__main__':
    import unittest
    from unittest.mock import patch, MagicMock, call
    import subprocess

    # 假设原代码中的函数已导入或定义在当前命名空间
    # 如果此测试代码与原文件在同一模块，直接引用即可；
    # 否则请确保 is_sensitive_command, run_command_with_approval 等可被导入。
    # 这里为了方便演示，直接复制上面的函数定义到测试环境（实际运行时无需重复定义）。

    class TestCmdExecutor(unittest.TestCase):

        # ---------- 测试敏感命令检测 ----------
        def test_is_sensitive_command_single_delete(self):
            self.assertTrue(is_sensitive_command("del file.txt"))
            self.assertTrue(is_sensitive_command("erase temp.dat"))
            self.assertTrue(is_sensitive_command("rm -rf folder"))

        def test_is_sensitive_command_format(self):
            self.assertTrue(is_sensitive_command("format D: /Q"))

        def test_is_sensitive_command_reg(self):
            self.assertTrue(is_sensitive_command("reg delete HKLM\\Software\\Test"))

        def test_is_sensitive_command_shutdown(self):
            self.assertTrue(is_sensitive_command("shutdown /s /t 0"))

        def test_is_sensitive_command_taskkill(self):
            self.assertTrue(is_sensitive_command("taskkill /F /IM notepad.exe"))

        def test_is_sensitive_command_icacls(self):
            self.assertTrue(is_sensitive_command("icacls C:\\Windows /grant User:F"))

        def test_is_sensitive_command_sc(self):
            self.assertTrue(is_sensitive_command("sc delete MyService"))

        def test_is_sensitive_command_powershell_with_risk(self):
            self.assertTrue(is_sensitive_command("powershell Remove-Item -Path C:\\Temp -Recurse"))

        def test_is_sensitive_command_net_user_add(self):
            self.assertTrue(is_sensitive_command("net user hacker pass /add"))

        def test_is_sensitive_command_non_sensitive(self):
            self.assertFalse(is_sensitive_command("dir"))
            self.assertFalse(is_sensitive_command("echo Hello"))
            self.assertFalse(is_sensitive_command("ipconfig /all"))
            self.assertFalse(is_sensitive_command("ping 8.8.8.8"))
            self.assertFalse(is_sensitive_command("type readme.txt"))

        def test_is_sensitive_command_multiple_commands(self):
            # 串联命令，只要有一个敏感即返回 True
            self.assertTrue(is_sensitive_command("echo start && del temp.txt"))
            self.assertTrue(is_sensitive_command("dir C:\\ || format D:"))
            self.assertTrue(is_sensitive_command("copy a.txt b.txt & shutdown /r"))
            self.assertTrue(is_sensitive_command("ping localhost | taskkill /F /IM explorer.exe"))
            self.assertFalse(is_sensitive_command("echo hello && dir && ipconfig"))

        def test_is_sensitive_command_path_prefix(self):
            # 带路径的命令名仍应识别
            self.assertTrue(is_sensitive_command(r"C:\Windows\System32\del.exe file.txt"))
            self.assertTrue(is_sensitive_command(r"d:\tools\rmdir /s folder"))

        def test_is_sensitive_command_word_boundary(self):
            # 不应误匹配包含敏感词子串的普通命令
            self.assertFalse(is_sensitive_command("model.exe"))          # 包含 "del" 子串？
            self.assertFalse(is_sensitive_command("deliver.exe"))        # 包含 "del"
            self.assertFalse(is_sensitive_command("reformat.exe"))       # 包含 "format"
            self.assertFalse(is_sensitive_command("shutdowner.exe"))     # 包含 "shutdown"
            # 但若单独出现 del 作为独立单词则敏感
            self.assertTrue(is_sensitive_command("deliver del file.txt"))  # 第二个 del 敏感

        # ---------- 测试 run_command_with_approval ----------
        @patch('subprocess.run')
        @patch('builtins.print')  # 避免输出干扰，实际测试不需要
        def test_non_sensitive_command_auto_approved(self, mock_print, mock_run):
            """非敏感命令应直接执行，不弹窗"""
            mock_run.return_value = MagicMock(stdout="Directory listing", stderr="")
            result = run_command_with_approval("dir C:\\")
            mock_run.assert_called_once()
            # 验证调用参数（忽略 shell, check, stdout, stderr, text, encoding, errors）
            args, kwargs = mock_run.call_args
            self.assertEqual(args[0], "dir C:\\")
            self.assertEqual(kwargs['shell'], True)
            self.assertEqual(kwargs['encoding'], 'utf-8')
            self.assertEqual(result, "Directory listing")

        @patch('subprocess.run')
        @patch('builtins.print')
        def test_non_sensitive_command_execution_failure(self, mock_print, mock_run):
            """非敏感命令执行失败时返回错误信息"""
            mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr="File not found")
            result = run_command_with_approval("type nonexistent.txt")
            mock_run.assert_called_once()
            self.assertIn("Command failed with error: File not found", result)

        @patch('subprocess.run')
        @patch('builtins.print')
        @patch('__main__.request_command_approval')  # 注意：需替换为实际模块名，此处假设测试代码与主代码在同一文件
        def test_sensitive_command_approved(self, mock_request, mock_print, mock_run):
            """敏感命令获得批准后应执行"""
            mock_request.return_value = {"status": "approved", "reason": None}
            mock_run.return_value = MagicMock(stdout="Volume in drive C is OS", stderr="")
            result = run_command_with_approval("format D: /Q")
            mock_request.assert_called_once_with("format D: /Q")  # 确认弹窗被调用
            mock_run.assert_called_once()
            self.assertIn("Volume in drive C is OS", result)

        @patch('subprocess.run')
        @patch('builtins.print')
        @patch('__main__.request_command_approval')
        def test_sensitive_command_rejected(self, mock_request, mock_print, mock_run):
            """敏感命令被驳回时不应执行子进程"""
            mock_request.return_value = {"status": "rejected", "reason": None}
            result = run_command_with_approval("del important.txt")
            mock_request.assert_called_once_with("del important.txt")
            mock_run.assert_not_called()  # 未执行
            self.assertEqual(result, "Command rejected by user.")

        @patch('subprocess.run')
        @patch('builtins.print')
        @patch('__main__.request_command_approval')
        def test_sensitive_command_rejected_with_reason(self, mock_request, mock_print, mock_run):
            """带理由驳回"""
            mock_request.return_value = {"status": "rejected_with_reason", "reason": "It's dangerous"}
            result = run_command_with_approval("rm -rf /")
            mock_request.assert_called_once()
            mock_run.assert_not_called()
            self.assertEqual(result, "Command rejected. Reason: It's dangerous")

        @patch('subprocess.run')
        @patch('builtins.print')
        @patch('__main__.request_command_approval')
        def test_sensitive_command_approved_but_fails(self, mock_request, mock_print, mock_run):
            """批准后执行失败"""
            mock_request.return_value = {"status": "approved", "reason": None}
            mock_run.side_effect = subprocess.CalledProcessError(5, 'cmd', stderr="Access denied")
            result = run_command_with_approval("reg delete HKLM\\Software")
            mock_run.assert_called_once()
            self.assertIn("Command failed with error: Access denied", result)

        @patch('subprocess.run')
        @patch('builtins.print')
        @patch('__main__.request_command_approval')
        def test_sensitive_command_cancelled(self, mock_request, mock_print, mock_run):
            """用户关闭窗口（意外情况）"""
            mock_request.return_value = {"status": None, "reason": None}
            result = run_command_with_approval("shutdown /r")
            mock_run.assert_not_called()
            self.assertEqual(result, "Command execution cancelled.")

    # 运行单元测试
    unittest.main()