disable_tool = False  # 禁用此工具

class DocumentProcessor:
    """
    一个用于处理文本文档的类，提供行数统计、内容提取和插入功能。
    所有方法直接接收完整文件路径进行操作
    """
    
    @staticmethod
    def count_text_lines(file_path):
        """
        返回指定文件的行数
        
        参数:
            file_path (str): 要处理的**完整文件路径**
            
        返回:
            int: 文件的行数
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return sum(1 for _ in file)
        except FileNotFoundError:
            print(f"错误: 文件路径 '{file_path}' 不存在")
            return -1
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return -1
    
    @staticmethod
    def get_text_lines(file_path, begin_line, end_line):
        """
        返回指定文件的部分内容，每行前附加行号
        
        参数:
            file_path (str): 要读取的**完整文件路径**
            begin_line (int): 起始行号(从1开始)
            end_line (int): 结束行号
            
        返回:
            list: 包含带行号文本行的列表，或错误时返回错误信息
        """
        lines = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, start=1):
                    if begin_line <= line_num <= end_line:
                        lines.append(f"[{line_num}] {line.rstrip()}")
                    elif line_num > end_line:
                        break
            
            return lines
        except FileNotFoundError:
            print(f"错误: 文件路径 '{file_path}' 不存在")
            return f"错误: 文件路径 '{file_path}' 不存在"
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return f"读取文件时出错: {e}"
    
    @staticmethod
    def add_text_line(file_path, insert_line, text):
        """
        在指定文件的第insert_line行后插入文本
        
        参数:
            file_path (str): 要修改的**完整文件路径**
            insert_line (int): 插入位置的行号(从1开始)
            text (list): 要插入的文本行列表
        """
        try:
            # 读取原文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
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
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(lines)
            
            return "文件已保存"
        except FileNotFoundError:
            print(f"错误: 文件路径 '{file_path}' 不存在")
            return f"错误: 文件路径 '{file_path}' 不存在"
        except Exception as e:
            print(f"写入文件时出错: {e}")
            return f"写入文件时出错: {e}"
        

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
        para_desc="\"file_path\":str - 要统计行数的**完整文件路径**。",
        warning="如果路径不存在或无法读取，将返回-1并打印错误信息。",
        func=txtreader.count_text_lines
    )

    invoker.register_tool(
        name="get_text_lines",
        summary="获取文本文件指定行范围的内容",
        description="读取指定文本文件中从begin_line到end_line的内容，并在每一行前附加行号标记。",
        para_desc="\"file_path\": str - 要读取的**完整文件路径**；\"begin_line\": int - 起始行号（从1开始）；\"end_line\": int - 结束行号。",
        warning="如果路径不存在或读取失败，返回空列表。行号范围超出文件实际行数时，只返回存在的行。你可能需要根据需要记忆重要信息的行号。",
        func=txtreader.get_text_lines
    )

    invoker.register_tool(
        name="add_text_line",
        summary="在文本文件指定行后插入文本",
        description="在指定文件的第insert_line行后插入字符串数组text（第0行表示文件开头），并保存文件。",
        para_desc="\"file_path\": str - 要插入内容的**完整文件路径**；\"insert_line\": int - 插入位置的行号（从1开始）；\"text\": list - 要插入的字符串数组，每个元素为一行。",
        warning="此操作会直接修改原文件，请确保有文件备份或确认操作无误。如果插入位置大于文件行数，将在文件末尾追加内容。",
        func=txtreader.add_text_line
    )

# 假设原始代码已存在，此处仅为补充测试部分
if __name__ == '__main__':
    import unittest
    import tempfile
    import os

    class TestDocumentProcessor(unittest.TestCase):
        """DocumentProcessor 类的单元测试"""

        def setUp(self):
            """每个测试前创建一个临时文件并写入初始内容（末尾带换行符）"""
            self.temp_file = tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False)
            self.file_path = self.temp_file.name
            self.initial_lines = ["第一行", "第二行", "第三行", "第四行"]
            # 确保文件末尾有换行符，避免追加新行时粘连
            self.temp_file.write('\n'.join(self.initial_lines) + '\n')
            self.temp_file.close()

        def tearDown(self):
            """每个测试后删除临时文件"""
            if os.path.exists(self.file_path):
                os.remove(self.file_path)

        # ---------- count_text_lines 测试 ----------
        def test_count_text_lines_normal(self):
            """正常统计行数"""
            count = DocumentProcessor.count_text_lines(self.file_path)
            self.assertEqual(count, len(self.initial_lines))

        def test_count_text_lines_file_not_found(self):
            """文件不存在时返回 -1"""
            count = DocumentProcessor.count_text_lines("/nonexistent/path/file.txt")
            self.assertEqual(count, -1)

        # ---------- get_text_lines 测试 ----------
        def test_get_text_lines_normal(self):
            """获取有效行范围，返回带行号的列表"""
            result = DocumentProcessor.get_text_lines(self.file_path, 2, 3)
            expected = ["[2] 第二行", "[3] 第三行"]
            self.assertEqual(result, expected)

        def test_get_text_lines_begin_out_of_range(self):
            """起始行超出文件行数，返回空列表"""
            result = DocumentProcessor.get_text_lines(self.file_path, 10, 12)
            self.assertEqual(result, [])

        def test_get_text_lines_end_out_of_range(self):
            """结束行超出文件行数，只返回存在的行"""
            result = DocumentProcessor.get_text_lines(self.file_path, 3, 10)
            expected = ["[3] 第三行", "[4] 第四行"]
            self.assertEqual(result, expected)

        def test_get_text_lines_file_not_found(self):
            """文件不存在时返回错误信息字符串"""
            result = DocumentProcessor.get_text_lines("/bad/path", 1, 5)
            self.assertTrue(isinstance(result, str))
            self.assertIn("错误", result)

        # ---------- add_text_line 测试 ----------
        def test_add_text_line_insert_middle(self):
            """在第2行后插入两行"""
            insert_text = ["新行A", "新行B"]
            result = DocumentProcessor.add_text_line(self.file_path, 2, insert_text)
            self.assertEqual(result, "文件已保存")

            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = [line.rstrip() for line in f.readlines()]
            expected = ["第一行", "第二行", "新行A", "新行B", "第三行", "第四行"]
            self.assertEqual(lines, expected)

        def test_add_text_line_insert_beginning_zero(self):
            """在文件开头插入（insert_line=0）"""
            insert_text = ["开头行"]
            DocumentProcessor.add_text_line(self.file_path, 0, insert_text)
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = [line.rstrip() for line in f.readlines()]
            expected = ["开头行"] + self.initial_lines
            self.assertEqual(lines, expected)

        def test_add_text_line_insert_beginning_negative(self):
            """负数 insert_line 同样在开头插入"""
            insert_text = ["负号开头"]
            DocumentProcessor.add_text_line(self.file_path, -5, insert_text)
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = [line.rstrip() for line in f.readlines()]
            expected = ["负号开头"] + self.initial_lines
            self.assertEqual(lines, expected)

        def test_add_text_line_insert_end(self):
            """插入位置大于总行数，追加到末尾（需确保原文件末尾有换行符）"""
            insert_text = ["末尾行"]
            DocumentProcessor.add_text_line(self.file_path, 100, insert_text)
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = [line.rstrip() for line in f.readlines()]
            expected = self.initial_lines + ["末尾行"]
            self.assertEqual(lines, expected)

        def test_add_text_line_file_not_found(self):
            """目标文件不存在时返回错误信息"""
            result = DocumentProcessor.add_text_line("/no/such/file.txt", 1, ["test"])
            self.assertTrue(isinstance(result, str))
            self.assertIn("错误", result)

    # 运行所有测试
    unittest.main(argv=[''], exit=False)