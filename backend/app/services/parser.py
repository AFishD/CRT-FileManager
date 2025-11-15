import os
import re
from typing import List, Dict, Any, Tuple
from ..models import FileData, TableData

def parse_markdown_file(file_path: str, root_dir: str) -> FileData:
    """
    解析单个Markdown文件，提取表格数据
    支持由分隔行拆分的多个表格
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise Exception(f"读取文件失败 {file_path}: {str(e)}")
    
    # 获取相对路径
    rel_path = os.path.relpath(file_path, root_dir)
    
    # 分割内容，查找标题和表格
    sections = split_content_by_headers(content)
    
    tables = []
    for section in sections:
        title, table_data_list = parse_section(section, file_path)
        if table_data_list:
            # 处理返回的表格列表（可能是单个表格或列表）
            if isinstance(table_data_list, list):
                # 如果是列表，添加所有表格
                for i, table_data in enumerate(table_data_list):
                    # 如果有多个表格，在标题后添加序号
                    table_title = title if i == 0 else f"{title} (Part {i+1})"
                    tables.append(TableData(
                        title=table_title,
                        header=table_data['header'],
                        rows=table_data['rows']
                    ))
            else:
                # 如果是单个表格
                tables.append(TableData(
                    title=title,
                    header=table_data_list['header'],
                    rows=table_data_list['rows']
                ))
    
    # 如果没有找到任何表格，尝试解析整个内容为表格
    if not tables:
        table_data_list = parse_table(content)
        if table_data_list:
            # 使用文件名（不含扩展名）作为标题
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            # 处理返回的表格列表（可能是单个表格或列表）
            if isinstance(table_data_list, list):
                # 如果是列表，添加所有表格
                for i, table_data in enumerate(table_data_list):
                    # 如果有多个表格，在标题后添加序号
                    table_title = file_name if i == 0 else f"{file_name} (Part {i+1})"
                    tables.append(TableData(
                        title=table_title,
                        header=table_data['header'],
                        rows=table_data['rows']
                    ))
            else:
                # 如果是单个表格
                tables.append(TableData(
                    title=file_name,
                    header=table_data_list['header'],
                    rows=table_data_list['rows']
                ))
    
    return FileData(
        filePath=rel_path,
        tables=tables
    )

def split_content_by_headers(content: str) -> List[Dict[str, Any]]:
    """
    根据Markdown标题分割内容，支持任意级别标题（###、####等）
    """
    sections = []
    lines = content.split('\n')
    
    current_section = {
        'title': None,
        'content': []
    }
    
    for line in lines:
        # 匹配任意级别的Markdown标题（###、####等）
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            # 如果已有内容，保存当前section
            if current_section['content']:
                sections.append(current_section)
            
            # 开始新的section
            current_section = {
                'title': header_match.group(2).strip(),
                'content': [line]
            }
        else:
            current_section['content'].append(line)
    
    # 添加最后一个section
    if current_section['content']:
        sections.append(current_section)
    
    return sections

def parse_section(section: Dict[str, Any], file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    解析单个section，提取标题和表格
    支持返回多个表格（由分隔行拆分）
    """
    title = section['title']
    content = '\n'.join(section['content'])
    
    table_data = parse_table(content)
    
    # 如果没有标题，使用文件名
    if not title and table_data:
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        title = file_name
    
    return title, table_data

def is_separator_row(cells):
    """
    检查一行是否为分隔行（所有单元格都是-或空格，或者包含进度标记）
    支持有进度列和没有进度列两种情况
    """
    for cell in cells:
        # 去掉空格后，检查单元格内容
        stripped = cell.strip()
        # 如果单元格不是空字符串，且不全是由-组成，也不是进度标记，则不是分隔行
        if stripped != '' and not all(c == '-' for c in stripped) and stripped not in ['[ ]', '[x]']:
            return False
    return True

def parse_table(content: str) -> Dict[str, Any]:
    """
    从内容中解析Markdown表格，检查并添加"进度"列
    识别分隔行并在数据中标记
    """
    # 查找表格
    table_pattern = r'(\|.*\|(?:\n\|.*\|)+)'
    table_match = re.search(table_pattern, content)
    
    if not table_match:
        return None
    
    table_text = table_match.group(1)
    lines = table_text.strip().split('\n')
    
    if len(lines) < 1:
        return None
    
    # 解析表头
    header_line = lines[0].strip()
    if not header_line.startswith('|') or not header_line.endswith('|'):
        return None
    
    headers = [h.strip() for h in header_line.split('|')[1:-1]]
    
    # 检查是否是分隔线（包含---）
    if len(lines) > 1 and '---' in lines[1]:
        data_start = 2
    else:
        data_start = 1
    
    # 解析数据行，识别分隔行
    rows = []
    header_count = len(headers)
    
    for line in lines[data_start:]:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if cells:  # 确保不是空行
                # 检查是否是分隔行
                if is_separator_row(cells):
                    # 如果是分隔行，添加空列表作为标记
                    rows.append([])  # 空列表表示分隔行
                else:
                    # 确保行数据与表头列数匹配
                    while len(cells) < header_count:
                        cells.append('')
                    if len(cells) > header_count:
                        cells = cells[:header_count]
                    rows.append(cells)
    
    if not rows:
        return None
    
    # 处理表格数据，检查并添加进度列
    return process_table_data(headers, rows)

def process_table_data(headers, rows):
    """
    处理表格数据，检查并添加进度列
    rows中包含空列表表示分隔行
    """
    if not rows:
        return None
    
    # 复制headers，避免修改原始列表
    table_headers = headers.copy()
    
    # 检查哪些行是数据行（非分隔行）
    data_rows = []
    for row in rows:
        if row:  # 如果不是分隔行（空列表）
            data_rows.append(row)
    
    # 如果没有数据行（所有行都是分隔行），也返回有效数据
    if not data_rows:
        return {
            'header': table_headers,
            'rows': rows
        }
    
    # 检查最后一列是否为进度列（内容为[ ]或[x]格式）
    is_progress_column = False
    if table_headers and data_rows:
        last_col_index = len(table_headers) - 1
        # 检查最后一列的内容是否符合进度格式
        progress_count = 0
        for row in data_rows:
            if len(row) > last_col_index:
                cell_value = row[last_col_index].strip()
                if cell_value in ['[ ]', '[x]']:
                    progress_count += 1
        
        # 如果超过一半的行符合进度格式，则认为最后一列是进度列
        if progress_count >= len(data_rows) * 0.5:
            is_progress_column = True
    
    # 确保所有行的列数与表头匹配
    header_count = len(table_headers)
    for i in range(len(rows)):
        if rows[i]:  # 如果不是分隔行（空列表）
            # 确保行有足够的列
            while len(rows[i]) < header_count:
                rows[i].append('')
            # 如果行有多余的列，截断
            if len(rows[i]) > header_count:
                rows[i] = rows[i][:header_count]
    
    # 如果没有进度列，添加它
    if not is_progress_column:
        table_headers.append('进度')
        
        # 为所有数据行添加进度列，填充默认值
        for i in range(len(rows)):
            if rows[i]:  # 如果不是分隔行
                rows[i].append('[ ]')
    else:
        # 确保进度列的格式正确
        last_col_index = len(table_headers) - 1
        for i in range(len(rows)):
            if rows[i]:  # 如果不是分隔行
                # 如果进度列为空，填充默认值
                if not rows[i][last_col_index] or rows[i][last_col_index].strip() == '':
                    rows[i][last_col_index] = '[ ]'
                # 确保格式正确（[ ] 或 [x]）
                elif rows[i][last_col_index] not in ['[ ]', '[x]']:
                    rows[i][last_col_index] = '[ ]'
    
    return {
        'header': table_headers,
        'rows': rows
    }

def scan_directory(root_dir: str) -> List[FileData]:
    """
    递归扫描目录，查找所有Markdown文件
    """
    if not os.path.exists(root_dir):
        raise Exception(f"目录不存在: {root_dir}")
    
    markdown_files = []
    for root, dirs, files in os.walk(root_dir):
        # 排除常见的隐藏目录和构建目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'dist', 'build']]
        
        for file in files:
            if file.lower().endswith('.md'):
                file_path = os.path.join(root, file)
                markdown_files.append(file_path)
    
    results = []
    for file_path in markdown_files:
        try:
            file_data = parse_markdown_file(file_path, root_dir)
            if file_data.tables:  # 只包含有表格的文件
                results.append(file_data)
        except Exception as e:
            print(f"警告: 解析文件失败 {file_path}: {str(e)}")
            continue
    
    return results