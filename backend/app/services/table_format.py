"""
Markdown 表格整形(按"显示宽度"对齐)

本地文件查看器(Typora / VSCode / GitHub)里的 Markdown 表格只有按显示宽度补空格
才能真正对齐:CJK 汉字与全角标点占 2 列、ASCII 占 1 列,直接用 len() 计算会错位。

目标形态(与 data/控制.md 的手工排版一致):

    | 序号 | 收藏品名称               | 所属版本      | 进度 |
    | ---- | ------------------------ | ------------- | ---- |
    | 01   | 希斯特工                 | 游戏本体      | [x]  |

规则:
  1. 每格渲染为  '|' + ' ' + 内容 + 补足到列宽的空格 + ' '  —— 最后一列同样补足,
     因此全表所有 '|' 竖直对齐
  2. 列宽 = 该列所有单元格(表头 + 数据行)的最大显示宽度,下限 3(保证 '---' 合法)
  3. 分隔行统一为  '| ' + '-' * 列宽 + ' ',不带 :---: 对齐冒号
  4. 缺少分隔行的表格补一行;表内的自定义分隔行(整行都是 -)按列宽重写

本模块只依赖标准库,可单独导入做离线测试:
    python -c "from table_format import format_markdown_tables; ..."
"""

import re
import unicodedata

# 列宽下限:少于 3 个 '-' 的分隔行部分渲染器不认,统一按 3 起步
MIN_COL_WIDTH = 3

# 零宽字符(零宽空格/连接符/变体选择符等)不占列宽
_ZERO_WIDTH_CODEPOINTS = frozenset([
    0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0xFE0E, 0xFE0F,
])

_FENCE_RE = re.compile(r'^\s*(```|~~~)')


def char_width(ch: str) -> int:
    """单个字符的显示宽度:0(组合符/零宽)、1(半角)、2(全角)"""
    code = ord(ch)
    if code < 32 or code in _ZERO_WIDTH_CODEPOINTS:
        return 0
    if unicodedata.combining(ch):
        return 0
    # W = Wide, F = Fullwidth;A(Ambiguous)按 1 处理(与终端/编辑器默认一致)
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1


def display_width(text: str) -> int:
    """字符串的显示宽度(\\| 这类转义按渲染后的一个字符计算)"""
    if not text:
        return 0
    if '\\|' in text:
        text = text.replace('\\|', '|')
    return sum(char_width(ch) for ch in text)


def split_row(line: str):
    """
    把 '| a | b |' 拆成 ['a', 'b'](元素已去首尾空格)。
    反斜杠转义的 \\| 不参与拆分;行首/行尾的竖线可缺省。
    非表格行(不以 | 开头)返回 None。
    """
    s = line.strip()
    if not s.startswith('|'):
        return None
    body = s[1:]
    if body.endswith('|'):
        body = body[:-1]

    cells = []
    cur = []
    i = 0
    length = len(body)
    while i < length:
        ch = body[i]
        if ch == '\\' and i + 1 < length:
            cur.append(ch)
            cur.append(body[i + 1])
            i += 2
            continue
        if ch == '|':
            cells.append(''.join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append(''.join(cur).strip())
    return cells


def is_separator_cell(cell: str) -> bool:
    """单元格是否形如 --- / :--- / ---: / :---:"""
    c = cell.strip()
    if not c or '-' not in c:
        return False
    return set(c) <= set('-:')


def is_separator_row(cells) -> bool:
    """整行是否都是分隔单元格"""
    if not cells:
        return False
    return all(is_separator_cell(c) for c in cells)


def _render_cell(text: str, width: int) -> str:
    pad = width - display_width(text)
    if pad < 0:
        pad = 0
    return ' ' + text + ' ' * pad + ' '


def _render_row(cells, widths) -> str:
    return '|' + ''.join(_render_cell(c, w) + '|' for c, w in zip(cells, widths))


def _render_separator(widths) -> str:
    return '|' + ''.join(' ' + '-' * w + ' |' for w in widths)


def format_table_block(lines):
    """
    整形一个表格块(连续的多行 '|...|'),返回新的行列表(不含换行符)。
    输入行数不足 2 时原样返回。
    """
    rows = [split_row(line) for line in lines]
    if len(rows) < 2 or any(r is None for r in rows):
        return list(lines)

    has_separator = is_separator_row(rows[1])
    header = rows[0]
    data_rows = rows[2:] if has_separator else rows[1:]

    # 列数取全表最大值:某行列数偏少时补空格,偏多时保留(不丢数据)
    ncol = max(len(r) for r in rows)
    if ncol <= 0:
        return list(lines)

    def fit(row):
        row = list(row)
        if len(row) < ncol:
            row.extend([''] * (ncol - len(row)))
        return row

    widths = [MIN_COL_WIDTH] * ncol
    for row in [header] + data_rows:
        for idx, cell in enumerate(fit(row)):
            w = display_width(cell)
            if w > widths[idx]:
                widths[idx] = w

    out = [_render_row(fit(header), widths), _render_separator(widths)]
    for row in data_rows:
        if is_separator_row(row):
            # 表内的自定义分隔行:表头样式统一,同样不带对齐冒号
            out.append(_render_separator(widths))
        else:
            out.append(_render_row(fit(row), widths))
    return out


def _line_eol(raw: str) -> str:
    if raw.endswith('\r\n'):
        return '\r\n'
    if raw.endswith('\n'):
        return '\n'
    if raw.endswith('\r'):
        return '\r'
    return ''


def detect_eol_style(raw: str) -> str:
    """文件的主换行风格:CRLF 占多数返回 '\\r\\n',否则返回 '\\n'"""
    crlf = raw.count('\r\n')
    bare_lf = raw.count('\n') - crlf
    return '\r\n' if crlf > bare_lf else '\n'


def to_lf(text: str) -> str:
    """
    统一成 LF 再处理。

    表格正则按 '\\n' 分行,CRLF 文本里行尾是 '\\r',跨行匹配会直接失败,
    所以读取后必须先归一化;写回时再用 detect_eol_style 还原。
    """
    if '\r' not in text:
        return text
    return text.replace('\r\n', '\n').replace('\r', '\n')


def format_markdown_tables(content: str) -> str:
    """
    整形文本里的所有 Markdown 表格,表格之外的原文原样保留(含换行符风格)。
    代码围栏(``` / ~~~)内的竖线不处理。
    """
    if not content:
        return content

    lines = content.splitlines(keepends=True)
    out = []
    i = 0
    total = len(lines)
    in_fence = False

    while i < total:
        raw = lines[i]
        body = raw.rstrip('\r\n')

        if _FENCE_RE.match(body):
            in_fence = not in_fence
            out.append(raw)
            i += 1
            continue

        if in_fence or not body.lstrip().startswith('|'):
            out.append(raw)
            i += 1
            continue

        # 收集连续的表块
        j = i
        while j < total and lines[j].rstrip('\r\n').lstrip().startswith('|'):
            j += 1
        block = lines[i:j]
        i = j

        if len(block) < 2:
            out.extend(block)
            continue

        eols = [_line_eol(b) for b in block]
        bodies = [b.rstrip('\r\n') for b in block]
        formatted = format_table_block(bodies)

        # 换行符按"源行"对齐:插入了分隔行时输出比输入多一行,若按输出下标
        # 取 eol,最后一行会拿到"文件末尾无换行"的空 eol,与前一行黏成一行
        rows = [split_row(b) for b in bodies]
        inserted_separator = not (len(rows) > 1 and rows[1] is not None
                                  and is_separator_row(rows[1]))
        if inserted_separator and len(formatted) == len(bodies) + 1:
            out.append(formatted[0] + eols[0])
            # 新增的分隔行沿用表头行的换行符(表头后面一定有换行,因为表格至少两行)
            out.append(formatted[1] + eols[0])
            for new_body, eol in zip(formatted[2:], eols[1:]):
                out.append(new_body + eol)
        else:
            for k, new_body in enumerate(formatted):
                out.append(new_body + eols[min(k, len(eols) - 1)])

    return ''.join(out)
