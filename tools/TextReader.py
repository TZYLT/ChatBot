

from logging import warn


disable_tool = False  # 禁用此工具

class DocumentProcessor:
    """
    一个用于处理文本文档的类，提供行数统计、内容提取和插入功能。
    """
    
    @staticmethod
    def count_text_lines(filename):
        """
        返回指定文件的行数
        
        参数:
            filename (str): 要处理的文件名
            
        返回:
            int: 文件的行数
        """
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return sum(1 for _ in file)
        except FileNotFoundError:
            print(f"错误: 文件 '{filename}' 不存在")
            return -1
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return -1
    
    @staticmethod
    def get_text_lines(filename, begin_line, end_line):
        """
        返回指定文件的部分内容，每行前附加行号
        
        参数:
            filename (str): 要读取的文件名
            begin_line (int): 起始行号(从1开始)
            end_line (int): 结束行号
            
        返回:
            list: 包含带行号文本行的列表，或错误时返回空列表
        """
        lines = []
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, start=1):
                    if begin_line <= line_num <= end_line:
                        lines.append(f"[{line_num}] {line.rstrip()}")
                    elif line_num > end_line:
                        break
            
            return lines
        except FileNotFoundError:
            print(f"错误: 文件 '{filename}' 不存在")
            return []
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return []
    
    @staticmethod
    def add_text_line(filename, insert_line, text):
        """
        在指定文件的第insert_line行后插入文本
        
        参数:
            filename (str): 要修改的文件名
            insert_line (int): 插入位置的行号(从1开始)
            text (list): 要插入的文本行列表
            
        返回:
            bool: 操作是否成功
        """
        try:
            # 读取原文件内容
            with open(filename, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # 处理插入位置
            if insert_line < 0:
                insert_pos = 0
            elif insert_line > len(lines):
                insert_pos = len(lines)
            else:
                insert_pos = insert_line
            
            # 插入新内容
            for i, new_line in enumerate(text):
                lines.insert(insert_pos + i, new_line + '\n')
            
            # 写回文件
            with open(filename, 'w', encoding='utf-8') as file:
                file.writelines(lines)
            
            return True
        except FileNotFoundError:
            print(f"错误: 文件 '{filename}' 不存在")
            return False
        except Exception as e:
            print(f"写入文件时出错: {e}")
            return False
        

def register(invoker):
    """
    插件注册入口，将自动被 ToolInvoker 扫描并调用
    """
    if disable_tool:
        return
    
    txtreader = DocumentProcessor()

    invoker.register_tool(
        name="count_text_lines",
        summary="统计文本文件行数",
        description="计算并返回指定文本文件的总行数。",
        para_desc="\"filename\":str - 要统计行数的文件路径。",
        warning="如果文件不存在或无法读取，将返回-1并打印错误信息。",
        func=txtreader.count_text_lines
    )

    invoker.register_tool(
        name="get_text_lines",
        summary="获取文本文件指定行范围的内容",
        description="读取指定文本文件中从begin_line到end_line的内容，并在每一行前附加行号标记。",
        para_desc="\"filename\": str - 要读取的文件路径；\"begin_line\": int - 起始行号（从1开始）；\"end_line\": int - 结束行号。",
        warning="如果文件不存在或读取失败，返回空列表。行号范围超出文件实际行数时，只返回存在的行。你可能需要根据需要记忆重要信息的行号。",
        func=txtreader.get_text_lines
    )

    invoker.register_tool(
        name="add_text_line",
        summary="在文本文件指定行后插入文本",
        description="在指定文件的第insert_line行后插入字符串数组text，并保存文件。",
        para_desc="\"filename\": str - 要插入内容的文件路径；\"insert_line\": int - 插入位置的行号（从1开始）；\"text\": list - 要插入的字符串数组，每个元素为一行。",
        warning="此操作会直接修改原文件，请确保有文件备份或确认操作无误。如果插入位置大于文件行数，将在文件末尾追加内容。",
        func=txtreader.add_text_line
    )