"""
table_format 单元测试(仅标准库,无需 fastapi/pydantic)

运行:
    python backend/tests/test_table_format.py
    python -m unittest discover -s backend/tests -v
"""

import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE_PATH = os.path.join(_HERE, '..', 'app', 'services', 'table_format.py')
_DATA_DIR = os.path.abspath(os.path.join(_HERE, '..', '..', 'data'))

# 直接按路径加载:table_format 必须保持零第三方依赖(离线可测)
_spec = importlib.util.spec_from_file_location('table_format', _MODULE_PATH)
tf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tf)


def line_width(line):
    return tf.display_width(line.rstrip('\r\n'))


def pipe_positions(line):
    """一行里所有未转义 '|' 的显示列位置"""
    positions = []
    col = 0
    text = line.rstrip('\r\n')
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            col += tf.char_width(text[i + 1])
            i += 2
            continue
        if text[i] == '|':
            positions.append(col)
        col += tf.char_width(text[i])
        i += 1
    return positions


def cells_of(line):
    """行的单元格文本(已 strip),用于校验整形不丢内容"""
    cells = tf.split_row(line.rstrip('\r\n'))
    return cells if cells is not None else None


class DisplayWidthTest(unittest.TestCase):
    def test_halfwidth_and_fullwidth(self):
        self.assertEqual(tf.display_width('abc'), 3)
        self.assertEqual(tf.display_width('中文'), 4)
        self.assertEqual(tf.display_width('所属版本'), 8)
        self.assertEqual(tf.display_width('扩展包2：AWE'), 12)
        self.assertEqual(tf.display_width('希斯特别行动队（空降兵）'), 24)

    def test_zero_width(self):
        self.assertEqual(tf.display_width(''), 0)
        self.assertEqual(tf.display_width('e\u0301'), 1)          # 组合重音
        self.assertEqual(tf.display_width('a\u200bb'), 2)         # 零宽空格
        self.assertEqual(tf.display_width('\ufe0f'), 0)           # 变体选择符

    def test_ambiguous_counts_one(self):
        # '·' 是 Ambiguous 宽度,与编辑器/终端默认一致按 1 计:6*2 + 1 = 13
        self.assertEqual(tf.display_width('索利德·斯内克'), 13)

    def test_escaped_pipe(self):
        self.assertEqual(tf.display_width('a\\|b'), 3)


class AlignTableTest(unittest.TestCase):
    SOURCE = (
        '| 序号 | 收藏品名称 | 所属版本 | 进度 |\n'
        '| :---: | :--- | :--- | :--- |\n'
        '| 1 | 希斯特工 | 游戏本体 | [x] |\n'
        '| 10 | 希斯特别行动队（空降兵） | 扩展包2：AWE | [ ] |\n'
    )

    def test_expected_layout(self):
        expected = (
            '| 序号 | 收藏品名称               | 所属版本     | 进度 |\n'
            '| ---- | ------------------------ | ------------ | ---- |\n'
            '| 1    | 希斯特工                 | 游戏本体     | [x]  |\n'
            '| 10   | 希斯特别行动队（空降兵） | 扩展包2：AWE | [ ]  |\n'
        )
        self.assertEqual(tf.format_markdown_tables(self.SOURCE), expected)

    def test_all_pipes_aligned_and_full_width(self):
        out = tf.format_markdown_tables(self.SOURCE).splitlines()
        widths = {line_width(l) for l in out}
        self.assertEqual(len(widths), 1, '每行显示宽度应一致: %r' % out)
        ref = pipe_positions(out[0])
        for line in out:
            self.assertEqual(pipe_positions(line), ref, '竖线未对齐: %r' % line)

    def test_separator_has_no_alignment_colons(self):
        out = tf.format_markdown_tables(self.SOURCE).splitlines()
        sep = out[1]
        self.assertNotIn(':', sep)
        # 列宽 = 该列所有非分隔行的最大显示宽度
        widths = [0] * len(cells_of(out[0]))
        for line in [out[0]] + out[2:]:
            for i, cell in enumerate(cells_of(line)):
                widths[i] = max(widths[i], tf.display_width(cell))
        self.assertEqual(cells_of(sep), ['-' * w for w in widths])
        self.assertEqual(len(sep), tf.display_width(sep))

    def test_progress_column_padded_like_others(self):
        out = tf.format_markdown_tables(self.SOURCE).splitlines()
        self.assertIn('| [x]  |', out[2])
        self.assertIn('| [ ]  |', out[3])

    def test_content_preserved(self):
        src = [c for l in self.SOURCE.splitlines() for c in cells_of(l)[:-0]]
        out = tf.format_markdown_tables(self.SOURCE).splitlines()
        got = [c for l in out for c in cells_of(l)]
        for cell in src:
            self.assertIn(cell, got)
        self.assertEqual(len(out), 4)

    def test_idempotent(self):
        once = tf.format_markdown_tables(self.SOURCE)
        twice = tf.format_markdown_tables(once)
        self.assertEqual(once, twice)


class EdgeCaseTest(unittest.TestCase):
    def test_inserts_missing_separator(self):
        src = '|下|左| 进度 |\n|1|1| [x] |\n|0|1| [ ] |\n'
        out = tf.format_markdown_tables(src).splitlines()
        self.assertEqual(len(out), 4)
        self.assertEqual(out[1], '| --- | --- | ---- |')
        self.assertEqual({line_width(l) for l in out}, {tf.display_width(out[0])})

    def test_min_column_width_is_three(self):
        src = '|n| 进度 |\n| --- | --- |\n|a| [x] |\n'
        out = tf.format_markdown_tables(src).splitlines()
        self.assertEqual(out[1], '| --- | ---- |')

    def test_inner_separator_row_normalized(self):
        src = (
            '| A | B | 进度 |\n'
            '| --- | --- | --- |\n'
            '| 1 | 2 | [x] |\n'
            '| -- | -- | -- |\n'
            '| 3 | 4 | [ ] |\n'
        )
        out = tf.format_markdown_tables(src).splitlines()
        self.assertEqual(len(out), 5)
        self.assertEqual(out[3], out[1], '表内分隔行应与表头分隔行同款')

    def test_ragged_rows_are_padded(self):
        src = '| A | B | C |\n| --- | --- | --- |\n| 1 |\n'
        out = tf.format_markdown_tables(src).splitlines()
        self.assertEqual({line_width(l) for l in out}, {tf.display_width(out[0])})
        self.assertEqual(cells_of(out[2]), ['1', '', ''])

    def test_escaped_pipe_stays_in_one_cell(self):
        src = '| A | B |\n| --- | --- |\n| a\\|b | c |\n'
        out = tf.format_markdown_tables(src).splitlines()
        self.assertEqual(cells_of(out[2]), ['a\\|b', 'c'])
        self.assertEqual({line_width(l) for l in out}, {tf.display_width(out[0])})

    def test_non_table_content_untouched(self):
        src = (
            '# 标题\n'
            '\n'
            '普通段落,没有表格。\n'
            '\n'
            '- 列表项\n'
            '\n'
            '| A | B |\n'
            '| --- | --- |\n'
            '| 中文 | b |\n'
            '\n'
            '结尾说明\n'
        )
        out = tf.format_markdown_tables(src)
        self.assertTrue(out.startswith('# 标题\n\n普通段落,没有表格。\n\n- 列表项\n\n'))
        self.assertTrue(out.endswith('\n结尾说明\n'))

    def test_single_pipe_line_untouched(self):
        src = '| not a table |\n'
        self.assertEqual(tf.format_markdown_tables(src), src)

    def test_fenced_code_block_untouched(self):
        src = '```\n| a | b |\n|---|---|\n| 1 | 2 |\n```\n'
        self.assertEqual(tf.format_markdown_tables(src), src)

    def test_crlf_preserved(self):
        src = '| 序号 | 名称 |\r\n| :---: | :--- |\r\n| 1 | 中文 |\r\n'
        out = tf.format_markdown_tables(src)
        self.assertEqual(out.count('\r\n'), 3)
        self.assertNotIn('\n', out.replace('\r\n', ''))  # 没有裸 LF
        self.assertEqual(out.split('\r\n')[:2], [
            '| 序号 | 名称 |',
            '| ---- | ---- |',
        ])

    def test_missing_trailing_newline_preserved(self):
        src = '| A | B |\n| --- | --- |\n| 中文 | b |'
        out = tf.format_markdown_tables(src)
        self.assertFalse(out.endswith('\n'))
        self.assertEqual(len(out.splitlines()), 3)

    def test_no_trailing_whitespace_added(self):
        src = '| A | B |\n| --- | --- |\n| a | b |\n'
        out = tf.format_markdown_tables(src)
        for line in out.splitlines():
            self.assertEqual(line, line.rstrip())


class EolStyleTest(unittest.TestCase):
    def test_detect_dominant_style(self):
        self.assertEqual(tf.detect_eol_style('a\r\nb\r\n'), '\r\n')
        self.assertEqual(tf.detect_eol_style('a\nb\n'), '\n')
        self.assertEqual(tf.detect_eol_style('a\r\nb\nc\n'), '\n')   # 少数 CRLF
        self.assertEqual(tf.detect_eol_style('a\nb\r\nc\r\n'), '\r\n')
        self.assertEqual(tf.detect_eol_style('no newline'), '\n')

    def test_to_lf(self):
        self.assertEqual(tf.to_lf('a\r\nb\rc\n'), 'a\nb\nc\n')
        self.assertEqual(tf.to_lf('a\nb\n'), 'a\nb\n')

    def test_roundtrip_preserves_crlf(self):
        raw = '| a | b |\r\n| --- | --- |\r\n| 中文 | x |\r\n'
        eol = tf.detect_eol_style(raw)
        out = tf.format_markdown_tables(tf.to_lf(raw))
        self.assertNotIn('\r', out)                      # 处理期统一 LF
        restored = out.replace('\n', eol)
        self.assertEqual(tf.to_lf(restored), out)
        self.assertEqual(restored.count('\r\n'), 3)


REFERENCE_FILES = [
    os.path.join(_DATA_DIR, '控制.md'),
    os.path.join(_DATA_DIR, '控制_原始.md'),
    os.path.join(_DATA_DIR, 'Lupin_The_Third.md'),
    os.path.join(_DATA_DIR, 'Terraria.md'),
    os.path.join(_DATA_DIR, 'Metal Gear - 合金装备', 'Metal Gear - 合金装备.md'),
]


@unittest.skipUnless(os.path.isdir(_DATA_DIR), 'data/ 目录不存在')
class RealFileTest(unittest.TestCase):
    """对真实数据文件做不变量校验:可反复整形、内容不丢失、竖线全对齐"""

    def _check_file(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            original = f.read()
        once = tf.format_markdown_tables(original)
        twice = tf.format_markdown_tables(once)

        self.assertEqual(once, twice, '反复整形结果必须稳定: %s' % path)

        def content_cells(text):
            """非分隔行的单元格内容(分隔行会被规范化,不参与比对)"""
            out = []
            for line in text.splitlines():
                if not line.lstrip().startswith('|'):
                    continue
                row = cells_of(line)
                if not row or tf.is_separator_row(row):
                    continue
                out.extend(c for c in row if c)
            return out

        src_cells = content_cells(original)
        out_cells = content_cells(once)
        self.assertEqual(sorted(src_cells), sorted(out_cells),
                         '%s 单元格内容被改变' % path)

        # 每个表格块内所有行的显示宽度必须一致(竖线因此对齐)
        in_block = False
        block_width = None
        for line in once.splitlines():
            if not line.lstrip().startswith('|'):
                in_block = False
                block_width = None
                continue
            w = tf.display_width(line)
            if not in_block:
                in_block = True
                block_width = w
                continue
            self.assertEqual(w, block_width,
                             '%s 表格行宽不一致: %r' % (path, line))

    def test_reference_files(self):
        checked = 0
        for path in REFERENCE_FILES:
            if os.path.exists(path):
                self._check_file(path)
                checked += 1
        if checked == 0:
            self.skipTest('data/ 下没有参照文件')


if __name__ == '__main__':
    unittest.main(verbosity=2)
