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