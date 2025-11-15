# CRT-Collectibles-Tracker 项目需求

## 项目概述
开发一个Markdown游戏收集品追踪器，具有复古CRT显示器风格。扫描本地Markdown文件，解析表格，通过Web界面展示和交互。更改每5分钟自动保存。Docker容器化部署。

## 技术栈
- **后端**: Python + FastAPI
- **前端**: Vue.js 3 + Vite
- **部署**: Docker

## 项目结构
```
/crt-tracker
├── backend/
│   ├── app/
│   │   ├── main.py           # API路由
│   │   ├── services/
│   │   │   ├── parser.py     # Markdown解析
│   │   │   └── writer.py     # 文件写入
│   │   └── models/
│   │       └── data.py       # Pydantic模型
│   └── Dockerfile
├── frontend/
│   ├── public/config.json    # CRT配置
│   ├── src/
│   │   ├── components/
│   │   │   ├── CRTEffect.vue # CRT效果
│   │   │   ├── FileTree.vue  # 文件树
│   │   │   └── TableView.vue # 表格视图
│   │   └── App.vue           # 主组件
│   └── package.json
└── docker-compose.yml
```

## 核心配置

### `frontend/public/config.json`
```json
{
  "crt_effects": {
    "enabled": true,
    "distortion": {"strength": 0.03, "zoom": 1.01},
    "glow": {"strength": "0.5px", "color": "rgba(255, 255, 255, 0.4)"},
    "blur": {"strength": "0.3px"}
  },
  "colors": {
    "text_default": "#FFFFFF",
    "text_completed": "#888888",
    "highlight_bg": "rgba(255, 255, 255, 0.1)"
  }
}
```

## 后端设计

### 数据模型 (`app/models/data.py`)
```python
from pydantic import BaseModel
from typing import List

class TableUpdate(BaseModel):
    filePath: str
    tableIndex: int
    newRows: List[List[str]]

class SaveRequest(BaseModel):
    updates: List[TableUpdate]
```

### 解析服务 (`app/services/parser.py`)
- `parse_markdown_file(file_path, root_dir)`: 解析单个文件
  - 按`#### Title` -> `Table`规则切分
  - 识别进度列（最后一列，[ ]或[x]格式）
  - 识别分隔行（全为`-`的行，用`[]`标记）
- `scan_directory(root_dir)`: 递归扫描所有`.md`文件

### 写入服务 (`app/services/writer.py`)
- `write_multiple_updates(updates: List[TableUpdate], root_dir: str)`: 批量写入更新，按文件分组处理
  - 按文件路径分组，每个文件只读一次
  - 遍历文件中的所有表格（即使未被修改）
  - 对每个表格调用 `update_table_in_content` 进行标准化
  - 每个文件只写一次
- `update_table_in_content(content, table_index, new_rows)`: 更新表格内容
  - **保留原始格式**: 不调用 `.strip()` 删除单元格内空格
  - **智能分列**: 使用 `rsplit('|', 1)` 精确找到最后一列位置
  - **统一标准化**: 保存时，整个文件的所有表格都会被处理
  - **向后兼容**: 保留 `write_updates_to_file` 函数以备测试使用
- `write_updates_to_file(update_data: TableUpdate, root_dir: str)`: 单文件写入（保留用于测试）

### API路由 (`app/main.py`)
- `GET /api/structure`: 返回目录结构
- `POST /api/save`: 保存更新
- 静态文件服务: `frontend/dist`

## 前端设计

### 状态管理 (`App.vue`)
状态变量: `allFilesData`, `currentFileIndex`, `currentTableIndex`, `currentView`, `fileTree`, `openDirectories`, `dirtyChanges`, `loading`, `error`, `saveError`

核心方法:
- `loadStructure()`: 加载数据
- `selectFile(filePath)`: 选择文件
- `prevTable()`/`nextTable()`: 切换表格
- `handleTableUpdate(update)`: 处理更新
- `saveChanges()`: 保存更改
- `handleKeydown(event)`: 键盘事件

键盘事件:
- ESC: 返回文件树
- ←/→: 切换表格
- ↑/↓: 移动选中行
- 空格/回车: 切换进度

### CRT效果 (`CRTEffect.vue`)
- 边缘形变: `perspective(800px) rotateX(1deg)`
- 文字辉光: `text-shadow`
- 轻微模糊: `filter: blur()`
- 整体缩放: `transform: scale()`
- CRT边框: `border-radius` + `box-shadow`

### 文件树 (`FileTree.vue`)
- 递归显示目录结构
- 使用`├──`、`└──`、`│   `符号
- 根节点: `Markdown_Tracker/`
- 文件符号: `■`
- 显示文件和表格数量

### 表格视图 (`TableView.vue`)
状态变量: `selectedRowIndex`, `columnWidths`, `headerHeight`

计算属性:
- `progressColumnIndex`: 进度列索引
- `visibleHeader`: 可见表头（排除进度列）
- `visibleRows`: 可见表格行（排除进度列）
- `highlightedRowIndex`: 高亮行索引

核心方法:
- `calculateColumnWidths()`: 自适应列宽计算（四阶段算法）
- `updateHeaderHeight()`: 更新表头高度用于滚动定位
- `updateMarqueeEffects()`: 更新流水屏动画效果
- `isRowCompleted(rowIndex)`: 检查是否完成
- `toggleRowCompletion(rowIndex)`: 切换完成状态
- `handleRowClick(rowIndex)`: 处理点击
- `handleWheel(event)`: 处理鼠标滚轮
- `handleKeydown(event)`: 处理键盘
- `isSeparatorRow(rowIndex)`: 检查分隔行（空列表）

键盘事件:
- ↑/↓: 移动选中行（跳过分隔行）
- 空格/回车: 切换进度

核心特性:
- **自适应列宽**: 根据内容和容器大小动态调整列宽，确保表格美观且实用
- **流水屏动画**: 长文本自动滚动显示，短文本保持静态
- **响应式布局**: 监听数据变化和窗口大小变化，实时重新计算布局
- **进度列隐藏**: 自动识别并隐藏最后一列（进度列），但保持数据完整性

样式:
- 选中行: 灰色背景
- 已完成: 灰色文字+删除线
- 分隔行: 透明背景（空列表标记）
- 滚动条: 隐藏但保持滚动功能（跨浏览器兼容）
- 表头: 固定定位（sticky），随滚动保持可见

### 顶部栏 (`HeaderBar.vue`)
- 显示当前标题
- 返回按钮
- 导航按钮（上一个/下一个表格）
- 保存按钮

## Docker部署

### Dockerfile
多阶段构建:
1. Frontend Build: Node.js环境
2. Final Image: Python环境

### 镜像源
- npm: 淘宝镜像
- pip: 清华镜像
- Debian: 阿里云镜像

## 功能特性

### 文件浏览
- 树形结构显示
- 递归扫描Markdown文件
- 只显示含表格的文件

### 表格操作
- 显示Markdown表格
- 自动识别进度列
- 支持多表格切换
- 键鼠操作

### 进度管理
- 点击或空格/回车切换状态
- 已完成: 灰色+删除线
- 未完成: 白色

### 自动保存
- 每5分钟自动保存
- 只保存更改的数据
- 失败显示错误提示

### 分隔行
- 识别`-`组成的行
- 显示为透明背景空行
- 禁止交互

## 使用说明

### 启动
```bash
docker-compose up --build
```

### 访问
`http://localhost`

### 流程
1. Markdown文件放入`data`目录
2. 刷新页面
3. 点击文件进入表格视图
4. 使用键鼠操作
5. 自动或手动保存

## 配置

### CRT效果
编辑`frontend/public/config.json`:
- `crt_effects.enabled`: 启用/禁用
- `crt_effects.distortion`: 形变参数
- `crt_effects.glow`: 辉光参数
- `crt_effects.blur`: 模糊参数
- `colors`: 颜色配置

### 自动保存间隔
编辑`frontend/src/App.vue`，修改`startAutoSave`函数（默认5分钟）

## 关键修复与优化

### 核心功能修复
1. **分隔行**: 识别`-`行，用`[]`标记，透明背景显示
2. **列数匹配**: 自动调整表头与数据列数
3. **选中行**: 鼠标和键盘统一，鼠标优先
4. **表格切换**: 切换时重置选中行到第一行

### 布局与显示优化
5. **禁用虚拟滚动**: 移除`viewportStartRow`, `maxVisibleRows`, `tableViewRef`等虚拟滚动相关代码
   - `visibleRows`直接返回所有表格行：`return props.tableData.rows`
   - 解决行高估算错误导致的空白区域问题
   - 简化代码逻辑，提高可维护性

6. **内容溢出修复**: 防止表格内容"穿出"容器边界
   - `App.vue`: `.content-area`添加`overflow: hidden`作为最外层剪裁边界
   - `TableView.vue`: `.table-view`添加`position: relative`为子元素提供定位上下文
   - `table`元素添加`display: block`和`overflow: hidden`限制内容不溢出

7. **滚动条隐藏**: 跨浏览器兼容的滚动条隐藏方案
   - Firefox: `scrollbar-width: none`
   - IE/Edge: `-ms-overflow-style: none`
   - Chrome/Safari: `::-webkit-scrollbar { display: none }`
   - 保持滚动功能的同时不显示滚动条

8. **表格样式优化**: 实现文本编辑器风格的表格布局
   - **边框模型**: `border-collapse: separate` + `border-spacing: 0 10px` 创建行间距
   - **表头固定**: `position: sticky; top: 20px` 配合 `box-shadow: 0 -20px 0 0 #000000` 创建遮罩，保持与标题栏间距
   - **智能边框**: 通过 `:first-child` 和 `:last-child` 选择器为表头和内容创建外框，内部无垂直线
   - **垂直分隔**: 仅 `td { border-left: 2px solid #ffffff; }` 创建列分隔线，无水平线干扰
   - **动态颜色**: `tr.completed td { border-color: #888888; }` 完成状态边框自动变灰
   - **零穿透**: 彻底解决 `border-collapse: collapse` 与 `position: sticky` 结合时的边框穿透问题

9. **表格宽度修复**: 确保表格占满容器宽度
   - `table`设置`min-width: 100%`防止根据内容缩小
   - 消除右侧空白区域

9. **初始布局修复**: 修复页面底部黑色区域问题
    - `App.vue`: `.content-area`使用flex布局，`.table-container`占满剩余空间
    - `TableView.vue`: `.table-view`高度100%，`table`保持自然高度
    - 实现内容垂直填充，无空白区域

### 流水屏动画效果 (新增)
10. **智能流水屏动画**: 为长文本实现无缝循环滚动效果
    - **固定行高**: 所有 `<td>` 设置 `height: 36px` + `white-space: nowrap` + `overflow: hidden`，确保行高一致，解决滚动逻辑问题
    - **智能溢出检测**: `updateMarqueeEffects()` 函数动态检测每个单元格内容是否溢出（`scrollWidth > clientWidth`）
    - **按需动画**: 仅对溢出单元格添加 `.is-overflowing` 类并启动动画，短文本保持静态显示
    - **无缝循环**: 通过动态克隆内容创建双份文本结构，配合 `transform: translateX(-50%)` 实现完美无缝循环
    - **速度恒定**: 动画时长基于内容实际像素宽度计算（50px/秒），确保不同长度文本滚动速度一致
    - **结构分离**: 使用 `.marquee-container` 包裹 `.marquee-text-part`，动画应用于容器，内容块使用 `margin-right` 控制间距
    - **状态管理**: 每次数据变化或窗口大小调整时重置状态（移除动画类和克隆节点），确保状态干净
    - **CSS动画**: `@keyframes marquee` 定义平滑滚动，通过 `animation-play-state` 控制播放/暂停

### 表格底部间距修复 (新增)
11. **表格底部固定间距**: 解决 CRT 效果暗角导致的最后一行辨认困难问题
    - **问题根源**: `height: 100%` 与 `padding-bottom` 的 CSS 布局矛盾，padding 被应用到可滚动区域内部而非固定视觉间距
    - **结构分离方案**: 将"负责占满高度的容器"和"负责滚动的容器"分离为两个独立 div
    - **外部容器** (`.table-view-container`): 设置 `flex-grow: 1`, `height: 100%`, `padding-bottom: 36px`，提供永久可见的底部间距
    - **内部容器** (`.table-view`): 设置 `height: 100%`, `overflow-y: auto`, 只负责滚动，实际高度被外部容器的 padding 压缩 36px
    - **最终效果**: 滚动条出现在已预留 36px 底部间距的容器内，无论是否滚动，间距始终存在，彻底解决最后一行被 CRT 暗角遮挡问题

### 自适应列宽算法 (新增)
12. **智能列宽计算**: 根据内容和容器大小动态调整表格列宽
    - **算法概述**: 四阶段计算流程，确保表格既美观又实用
    - **核心实现**:
        - **Stage 1 - 初始化**: 获取容器净宽度（减去内边距），设置常量（CELL_PADDING=20px, MAX_WIDTH=500px, MIN_WIDTH=60px）
        - **Stage 2 - 测量**: 创建临时 `<span>` 元素精确测量每列表头和所有单元格内容的像素宽度，计算理想宽度（内容宽度 + 内边距，不超过最大值）
        - **Stage 3 - 决策**:
            - **未溢出场景**（总理想宽度 ≤ 容器宽度）: 按比例拉伸列宽填满容器
            - **溢出场景**（总理想宽度 > 容器宽度）: 按比例压缩列宽，确保每列不低于最小宽度
        - **Stage 4 - 应用**: 将计算结果设置到 `<colgroup><col>` 元素，触发 Vue 响应式更新
    - **关键特性**:
        - **精确测量**: 使用 DOM API 获取内容实际像素宽度，非估算
        - **智能适配**: 内容少时拉伸填充，内容多时压缩显示
        - **边界保护**: 最小宽度防止列过窄，最大宽度防止列过宽
        - **响应式**: 监听数据变化和容器大小变化（ResizeObserver），实时重新计算
    - **与流水屏动画协调**: 列宽计算完成后触发 `updateMarqueeEffects()`，确保动画基于最终单元格宽度判断溢出
    - **水平溢出修复**:
        - **问题根源**: `clientWidth` 包含内边距，算法高估可用空间约40px
        - **解决方案**: 使用 `getComputedStyle` 获取实际内边距并扣除，修正 `CELL_PADDING` 匹配CSS（20px），为 `th/td` 添加 `box-sizing: border-box`
        - **最终效果**: 表格总宽度完美等于容器净宽度，消除水平滚动条

### writer.py 最终修复版本 (新增)
13. **外科手术式表格修改**: 完全重写 `writer.py`，实现最小侵入性修改
    - **问题背景**: 原始实现会重建整个表格，删除用户精心调整的空格和格式
    - **核心目标**: 只修改进度列和分隔行，100%保留其他内容
    
    #### 关键改进
    
    **(1) 分隔行对齐修复**
    - **问题**: 进度列前一列的分隔行被添加了两个空格，导致无法对齐
    - **修复**: 移除 `left` 和 `|` 之间的多余空格
    - **旧代码**: `f"{left} | ------------ |{right}"`（两个空格）
    - **新代码**: `f"{left}| ------------ |{right}"`（一个空格，完美对齐）
    
    **(2) 默认进度状态添加**
    - **问题**: 只添加 `[x]`，未添加 `[ ]`，导致未修改的行没有进度列
    - **修复**: 修改 `update_table_in_content` 函数，确保所有数据行都添加进度状态
    - **逻辑**: 默认值为 `'[ ]'`，如果有更新数据则覆盖为 `[x]`
    
    **(3) 文件级批量处理**
    - **问题**: 只修改被交互的表格，其他表格保持原样（可能没有进度列）
    - **修复**: 重构 `write_multiple_updates` 函数，按文件分组处理
    - **新流程**:
        1. 按文件路径对更新进行分组
        2. 对每个文件只读一次
        3. 遍历文件中的所有表格（即使未被修改）
        4. 对每个表格调用 `update_table_in_content` 进行标准化
        5. 对每个文件只写一次
    
    #### 函数签名变化
    
    ```python
    def write_multiple_updates(updates: List[TableUpdate], root_dir: str) -> Dict[str, Any]:
        """
        批量写入多个更新。
        按文件分组，对每个文件进行一次完整的读写操作，
        确保文件内的所有表格都被统一标准化。
        """
        # 按文件路径分组
        updates_by_file = defaultdict(list)
        for update in updates:
            updates_by_file[update.filePath].append(update)
        
        # 对每个文件：读取 -> 处理所有表格 -> 写入
        # ...
    
    def update_table_in_content(content: str, table_index: int, new_rows: Optional[List[List[str]]]) -> str:
        """
        在内容中定位并更新单个表格。
        new_rows 是可选的。如果为 None，则仅执行标准化（添加默认进度列）。
        """
        # 检测原始表格是否已有进度列
        # 如果没有，为所有行添加进度列（默认 [ ]）
        # 如果有，只在有更新数据时修改现有进度列
        # ...
    ```
    
    #### 核心特性
    
    - **保留原始格式**: 不调用 `.strip()` 删除单元格内空格
    - **智能分列**: 使用 `rsplit('|', 1)` 精确找到最后一列位置
    - **统一标准化**: 保存时，整个文件的所有表格都会被处理
    - **向后兼容**: 保留 `write_updates_to_file` 函数以备测试使用
    
    #### 最终效果
    
    - ✅ 保留所有原始空格和格式
    - ✅ 正确添加新列，使用 `|` 分隔符
    - ✅ 分隔行使用 `| ------------ |` 格式
    - ✅ 所有数据行都添加 `[ ]` 或 `[x]` 状态
    - ✅ 只修改进度列，不影响其他内容
    - ✅ 保存时，整个文件的所有表格都会被统一标准化
    
    程序现在会像"彬彬有礼的协作者"，只修改它需要修改的部分，完美保留您在文本编辑器中精心调整的所有格式！