import os
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
from ..models import TableUpdate

def write_multiple_updates(updates: List[TableUpdate], root_dir: str) -> Dict[str, Any]:
    """
    批量写入多个更新。按文件分组，对每个文件进行一次完整的读写操作，
    确保文件内的所有表格都被统一标准化。
    """
    results = {
        'success': True,
        'updated_files': [],
        'errors': []
    }
    
    updates_by_file = defaultdict(list)
    for update in updates:
        updates_by_file[update.filePath].append(update)

    for file_path_rel, file_updates in updates_by_file.items():
        try:
            file_path_abs = os.path.join(root_dir, file_path_rel)
            with open(file_path_abs, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            update_lookup = {up.tableIndex: up.newRows for up in file_updates}
            
            # 我们需要动态地查找表格，因为每次更新都会改变内容和表格位置
            i = 0
            while True:
                table_pattern = r'(\|.*\|(?:\n\|.*\|)+)'
                tables = list(re.finditer(table_pattern, current_content, re.MULTILINE))
                if i >= len(tables):
                    break
                
                rows_to_update = update_lookup.get(i)
                current_content = update_table_in_content(current_content, i, rows_to_update)
                i += 1

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
    修复了因分隔行导致的数据索引错位问题。
    """
    table_pattern = r'(\|.*\|(?:\n\|.*\|)+)'
    tables = list(re.finditer(table_pattern, content, re.MULTILINE))
    
    if table_index >= len(tables):
        return content
    
    target_table = tables[table_index]
    original_table_text = target_table.group(1)
    
    original_lines = original_table_text.strip().split('\n')
    new_table_lines = []
    
    original_header_cells = [h.strip() for h in original_lines[0].split('|')[1:-1]]
    has_original_progress_col = original_header_cells and original_header_cells[-1] == '进度'
    
    # FIXED: 使用一个统一的游标来同步 new_rows 和 original_lines
    new_rows_cursor = 0
    
    for i, line in enumerate(original_lines):
        line = line.rstrip()
        
        is_header = i == 0
        is_main_separator = i == 1 and '---' in line

        if is_header or is_main_separator:
            # 处理表头和主分隔行
            if not has_original_progress_col:
                parts = line.rsplit('|', 1)
                if len(parts) == 2:
                    left, right = parts
                    if is_header:
                        new_line = f"{left}| 进度 |{right}"
                    else: # is_main_separator
                        new_line = f"{left}| ---- |{right}"
                    new_table_lines.append(new_line)
                else:
                    new_table_lines.append(line)
            else:
                new_table_lines.append(line)
            continue

        # --- 从这里开始，处理所有对应 new_rows 的行（数据行和自定义分隔行）---
        
        # 安全检查，防止索引越界
        if new_rows and new_rows_cursor >= len(new_rows):
            new_table_lines.append(line) # 如果 new_rows 数据不够，保留原始行
            continue

        cells_stripped = [c.strip() for c in line.split('|')[1:-1]]
        is_custom_separator = not is_header and cells_stripped and all(c and all(char == '-' for char in c) for c in cells_stripped)
        is_data_row = not is_header and not is_main_separator and not is_custom_separator

        # ----------------------------------------
        # Case 1: 需要添加新的进度列
        # ----------------------------------------
        if not has_original_progress_col:
            parts = line.rsplit('|', 1)
            if len(parts) == 2:
                left, right = parts
                if is_data_row:
                    progress_state = '[ ]' # 默认值
                    # 从 new_rows 获取正确的状态
                    if new_rows and new_rows[new_rows_cursor]:
                        progress_state = new_rows[new_rows_cursor][-1].strip()
                    new_line = f"{left}| {progress_state} |{right}"
                elif is_custom_separator:
                    new_line = f"{left}| ---- |{right}"
                else: # 其他未知行
                    new_line = line
                new_table_lines.append(new_line)
            else:
                new_table_lines.append(line)
        
        # ----------------------------------------
        # Case 2: 已经有进度列，只需更新
        # ----------------------------------------
        else:
            if is_data_row and new_rows: # 只在有更新数据时才修改现有进度列
                progress_state = new_rows[new_rows_cursor][-1].strip()
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
            else: # 如果是自定义分隔行或没有更新数据，保留原样
                new_table_lines.append(line)
        
        # FIXED: 无论当前行是数据行还是自定义分隔行，游标都必须前进
        new_rows_cursor += 1

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