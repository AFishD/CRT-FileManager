import os
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
from ..models import TableUpdate

def write_multiple_updates(updates: List[TableUpdate], root_dir: str) -> Dict[str, Any]:
    """
    批量写入多个更新。
    这是新的核心逻辑：按文件分组，对每个文件进行一次完整的读写操作，
    确保文件内的所有表格都被统一标准化。
    """
    results = {
        'success': True,
        'updated_files': [],
        'errors': []
    }
    
    # 按文件路径对更新进行分组
    updates_by_file = defaultdict(list)
    for update in updates:
        updates_by_file[update.filePath].append(update)

    for file_path_rel, file_updates in updates_by_file.items():
        try:
            file_path_abs = os.path.join(root_dir, file_path_rel)
            
            # 1. 对每个文件只读一次
            with open(file_path_abs, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # 找到文件中的所有表格
            table_pattern = r'(\|.*\|(?:\n\|.*\|)+)'
            tables = list(re.finditer(table_pattern, current_content, re.MULTILINE))
            num_tables = len(tables)

            # 创建一个从 tableIndex 到 newRows 的查找字典
            update_lookup = {up.tableIndex: up.newRows for up in file_updates}

            # 2. 依次处理文件中的每一个表格
            # 即使某个表格没有被前端修改，我们也要调用函数来确保它被标准化（添加进度列）
            for i in range(num_tables):
                rows_to_update = update_lookup.get(i)
                # 使用一个临时变量来累积更新
                current_content = update_table_in_content(current_content, i, rows_to_update)

            # 3. 对每个文件只写一次
            with open(file_path_abs, 'w', encoding='utf-8') as f:
                f.write(current_content)
            
            results['updated_files'].append(file_path_rel)

        except Exception as e:
            results['success'] = False
            results['errors'].append({
                'file': file_path_rel,
                'error': str(e)
            })
    
    return results

def update_table_in_content(content: str, table_index: int, new_rows: Optional[List[List[str]]]) -> str:
    """
    在内容中定位并更新单个表格。
    现在 new_rows 是可选的。如果为 None，则仅执行标准化（添加默认进度列）。
    """
    table_pattern = r'(\|.*\|(?:\n\|.*\|)+)'
    # 注意：我们必须从头查找，因为 content 在循环中可能会改变
    tables = list(re.finditer(table_pattern, content, re.MULTILINE))
    
    if table_index >= len(tables):
        # 如果索引超出范围（可能因为上一个表格更新改变了内容），直接返回原始内容
        return content
    
    target_table = tables[table_index]
    original_table_text = target_table.group(1)
    
    original_lines = original_table_text.strip().split('\n')
    new_table_lines = []
    
    original_header_cells = [h.strip() for h in original_lines[0].split('|')[1:-1]]
    has_original_progress_col = original_header_cells and original_header_cells[-1] == '进度'
    
    data_row_index = 0
    
    for i, line in enumerate(original_lines):
        line = line.rstrip()
        
        is_header = i == 0
        is_main_separator = i == 1 and '---' in line
        cells_stripped = [c.strip() for c in line.split('|')[1:-1]]
        is_custom_separator = not is_header and cells_stripped and all(c and all(char == '-' for char in c) for c in cells_stripped)
        is_data_row = not is_header and not is_main_separator and not is_custom_separator

        if not has_original_progress_col:
            parts = line.rsplit('|', 1)
            if len(parts) == 2:
                left, right = parts
                
                if is_header:
                    new_line = f"{left}| 进度 |{right}"
                elif is_main_separator or is_custom_separator:
                    new_line = f"{left}| ---- |{right}"
                elif is_data_row:
                    # FIXED (问题2): 无论 new_rows 是否存在，都为数据行添加进度列
                    progress_state = '[ ]'  # 默认状态
                    if new_rows and data_row_index < len(new_rows) and new_rows[data_row_index]:
                        progress_state = new_rows[data_row_index][-1].strip()
                    
                    new_line = f"{left}| {progress_state}  |{right}"
                    data_row_index += 1
                else:
                    new_line = line
                new_table_lines.append(new_line)
            else:
                new_table_lines.append(line)
        
        else: # 如果已有进度列
            if is_data_row and new_rows: # 只在有更新数据时才修改现有进度列
                if data_row_index < len(new_rows) and new_rows[data_row_index]:
                    progress_state = new_rows[data_row_index][-1].strip()
                    cells = line.split('|')
                    if len(cells) > 2:
                        original_cell = cells[-2]
                        stripped_cell = original_cell.strip()
                        leading_space = original_cell[:original_cell.find(stripped_cell)] if stripped_cell else ' '
                        trailing_space = original_cell[original_cell.rfind(stripped_cell)+len(stripped_cell):] if stripped_cell else ' '
                        cells[-2] = f"{leading_space}{progress_state}{trailing_space}"
                        new_table_lines.append('|'.join(cells))
                    else:
                        new_table_lines.append(line)
                    data_row_index += 1
                else:
                     new_table_lines.append(line)
            else:
                new_table_lines.append(line)

    new_table_text = '\n'.join(new_table_lines)
    
    return content[:target_table.start()] + new_table_text + content[target_table.end():]

# 单文件写入函数现在不再被直接调用，但可以保留以备将来使用或测试
def write_updates_to_file(update_data: TableUpdate, root_dir: str) -> bool:
    file_path = os.path.join(root_dir, update_data.filePath)
    if not os.path.exists(file_path):
        raise Exception(f"文件不存在: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    updated_content = update_table_in_content(
        original_content, 
        update_data.tableIndex, 
        update_data.newRows
    )
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    return True