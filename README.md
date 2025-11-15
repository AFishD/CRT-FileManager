# CRT-Collectibles-Tracker

一个拥有复古CRT（阴极射线管）显示器风格的Markdown游戏收集品追踪器Web应用。扫描本地Markdown文件，解析表格数据，通过Web界面展示和交互，更改每5分钟自动保存。

## 功能特性

- 📁 **智能文件扫描**: 递归扫描本地Markdown文件，自动解析表格数据
- ✅ **自动进度管理**: 智能检测并自动添加"进度"列（如不存在），支持 `[ ]` 和 `[x]` 状态切换
- 🎮 **完整键盘导航**: 方向键移动、空格/回车切换、ESC返回文件树
- 🖱️ **鼠标交互**: 点击切换状态、悬停高亮、滚轮滚动
- 💾 **双模式保存**: 每5分钟自动保存 + 手动保存按钮
- 🖥️ **复古CRT效果**: 可配置的阴极射线管显示器视觉效果
- 🐳 **Docker容器化**: 一键部署，支持国内镜像源加速
- 🔤 **完整中文支持**: 界面和文档全中文
- 📊 **智能表格布局**: 自适应列宽、流水屏动画、分隔行识别
- 🌳 **树形文件浏览**: 递归显示目录结构，只展示含表格的文件

## 技术栈

- **后端**: Python 3.10 + FastAPI 0.104.1
- **前端**: Vue.js 3.3.8 (Composition API) + Vite 5.0.0
- **部署**: Docker + Docker Compose
- **数据模型**: Pydantic 2.5.0

## 快速开始

### Docker部署（推荐）

1. 将Markdown文件放入 `./data` 目录
2. 构建并启动容器：

```bash
docker-compose up --build
```

3. 访问 `http://localhost`

容器特性：
- 多阶段构建（前端构建 + Python运行时）
- 国内镜像源加速（npm淘宝源、pip清华源、Debian阿里云源）
- 健康检查机制
- 内存限制4GB

### 开发环境

#### 后端开发

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## Markdown文件格式

应用支持标准Markdown表格格式，自动识别以下两种结构：

### 带标题的表格

```markdown
### 一周目
| 武器名字   | 武器种类   | 武器收集地点  |
| ---------- | ---------- | ------------- |
| 诺威之长剑 | Long Sword | 第一章 第一节 |
| 艾丽丝之枪 | Spear      | 第一章 第三节 |
```

### 无标题的表格

```markdown
| 武器名字   | 武器种类   | 武器收集地点  |
| ---------- | ---------- | ------------- |
| 诺威之长剑 | Long Sword | 第一章 第一节 |
```

### 智能处理规则

- **自动添加进度列**: 检测表格是否包含进度列（最后一列 `[ ]` 或 `[x]` 格式），如不存在则自动添加
- **分隔行识别**: 识别由 `-` 组成的行，显示为透明背景空行，禁止交互
- **默认状态填充**: 为所有行填充默认进度值 `[ ]`
- **无标题处理**: 无标题时使用文件名作为标题

## 交互操作

### 键盘操作

| 按键 | 功能 |
|------|------|
| `↑` / `↓` | 上下移动选中行（自动跳过分隔行） |
| `←` / `→` | 切换表格（文件含多个表格时） |
| `空格` / `回车` | 切换当前行的完成状态 |
| `ESC` | 从表格视图返回文件树 |
| `鼠标滚轮` | 滚动长表格 |

### 鼠标操作

- **点击**: 切换行的完成状态
- **悬停**: 高亮显示行（灰色背景）

### 保存机制

- **自动保存**: 每5分钟自动保存所有更改到原Markdown文件
- **手动保存**: 点击右上角"保存"按钮立即保存
- **保存状态**: 界面底部显示保存状态（成功/失败）
- **智能写入**: 只修改进度列和分隔行，100%保留其他内容和格式

## CRT效果配置

编辑 `frontend/public/config.json` 可调整视觉效果：

```json
{
  "crt_effects": {
    "enabled": true,
    "distortion": {
      "strength": 0.03,
      "zoom": 1.01
    },
    "glow": {
      "strength": "0.5px",
      "color": "rgba(255, 255, 255, 0.4)"
    },
    "blur": {
      "strength": "0.3px"
    }
  },
  "colors": {
    "text_default": "#FFFFFF",
    "text_completed": "#888888",
    "highlight_bg": "rgba(255, 255, 255, 0.1)"
  }
}
```

### 配置项说明

- `crt_effects.enabled`: 启用/禁用CRT效果
- `crt_effects.distortion`: 边缘形变参数（perspective + rotateX）
- `crt_effects.glow`: 文字辉光效果（text-shadow）
- `crt_effects.blur`: 轻微模糊效果
- `colors`: 文字和背景颜色配置

## 核心算法与优化

### 自适应列宽算法

四阶段智能计算流程，确保表格美观实用：

1. **初始化**: 获取容器净宽度，设置常量（CELL_PADDING=20px, MAX_WIDTH=500px, MIN_WIDTH=60px）
2. **测量**: 创建临时 `<span>` 元素精确测量每列表头和所有单元格内容的像素宽度
3. **决策**:
   - 未溢出场景（总理想宽度 ≤ 容器宽度）: 按比例拉伸列宽填满容器
   - 溢出场景（总理想宽度 > 容器宽度）: 按比例压缩列宽，确保每列不低于最小宽度
4. **应用**: 将计算结果设置到 `<colgroup><col>` 元素，触发Vue响应式更新

### 流水屏动画效果

为长文本实现无缝循环滚动：

- **智能检测**: 动态检测每个单元格内容是否溢出（`scrollWidth > clientWidth`）
- **按需动画**: 仅对溢出单元格启动动画，短文本保持静态
- **无缝循环**: 通过动态克隆内容创建双份文本结构，配合 `transform: translateX(-50%)` 实现完美循环
- **速度恒定**: 动画时长基于内容实际像素宽度计算（50px/秒）

### 表格写入优化

`writer.py` 实现最小侵入性修改：

- **保留原始格式**: 不调用 `.strip()` 删除单元格内空格
- **智能分列**: 使用 `rsplit('|', 1)` 精确找到最后一列位置
- **统一标准化**: 保存时，整个文件的所有表格都会被处理
- **向后兼容**: 保留 `write_updates_to_file` 函数以备测试使用

### 布局修复

- **内容溢出修复**: `.content-area` 添加 `overflow: hidden` 作为最外层剪裁边界
- **滚动条隐藏**: 跨浏览器兼容方案（Firefox/IE/Edge/Chrome/Safari）
- **表格样式优化**: `border-collapse: separate` + `border-spacing: 0 10px` 创建行间距
- **表头固定**: `position: sticky` 配合 `box-shadow` 创建遮罩，保持与标题栏间距
- **底部间距**: 结构分离方案，确保CRT暗角不遮挡最后一行

## API接口

### `GET /api/structure`

返回所有Markdown文件的结构化数据：

```json
{
  "files": [
    {
      "filePath": "游戏收集/一周目.md",
      "tables": [
        {
          "title": "一周目",
          "header": ["武器名字", "武器种类", "武器收集地点", "进度"],
          "rows": [
            ["诺威之长剑", "Long Sword", "第一章 第一节", "[ ]"],
            ["艾丽丝之枪", "Spear", "第一章 第三节", "[x]"]
          ]
        }
      ]
    }
  ]
}
```

### `POST /api/save`

保存表格更新到Markdown文件：

**请求体**:
```json
{
  "updates": [
    {
      "filePath": "游戏收集/一周目.md",
      "tableIndex": 0,
      "newRows": [
        ["诺威之长剑", "Long Sword", "第一章 第一节", "[x]"],
        ["艾丽丝之枪", "Spear", "第一章 第三节", "[x]"]
      ]
    }
  ]
}
```

**响应**:
```json
{
  "success": true,
  "message": "保存成功"
}
```

### `GET /health`

健康检查接口，返回服务状态。

## 项目结构

```
/crt-tracker
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI路由和静态文件服务
│   │   ├── services/
│   │   │   ├── parser.py        # Markdown解析服务
│   │   │   └── writer.py        # 文件写入服务
│   │   └── models/
│   │       └── data.py          # Pydantic数据模型
│   ├── Dockerfile               # 多阶段构建Dockerfile
│   └── requirements.txt         # Python依赖
├── frontend/
│   ├── public/
│   │   └── config.json          # CRT效果配置文件
│   ├── src/
│   │   ├── assets/
│   │   │   └── main.css         # 全局样式
│   │   ├── components/
│   │   │   ├── CRTEffect.vue    # CRT视觉效果组件
│   │   │   ├── FileTree.vue     # 文件树组件
│   │   │   ├── HeaderBar.vue    # 顶部栏组件
│   │   │   └── TableView.vue    # 表格视图组件
│   │   ├── App.vue              # 主应用组件
│   │   └── main.js              # 应用入口
│   ├── package.json             # Node.js依赖
│   └── vite.config.js           # Vite构建配置
├── data/                        # Markdown文件存放目录
├── docker-compose.yml           # Docker部署配置
├── PROJECT_PROMPT.md            # 项目需求文档
└── README.md                    # 项目说明文档
```

## 使用流程

1. **准备数据**: 将Markdown文件放入 `./data` 目录（支持子目录）
2. **启动服务**: 运行 `docker-compose up --build`
3. **浏览文件**: 访问 `http://localhost`，在文件树中选择文件
4. **查看表格**: 点击文件进入表格视图，使用左右箭头切换多个表格
5. **更新进度**: 使用键盘或鼠标切换收集品状态（`[ ]` 未完成 / `[x]` 已完成）
6. **保存更改**: 系统自动每5分钟保存，或手动点击"保存"按钮

## 开发说明

### 后端服务

- **入口**: `backend/app/main.py`
- **扫描服务**: `scan_directory()` 递归扫描所有 `.md` 文件
- **解析规则**: 按 `#### Title` -> `Table` 规则切分，识别进度列和分隔行
- **写入服务**: `write_multiple_updates()` 批量处理，按文件分组最小化IO

### 前端组件

- **状态管理**: `App.vue` 使用Composition API管理全局状态
- **CRT效果**: `CRTEffect.vue` 实现边缘形变、文字辉光、轻微模糊
- **文件树**: `FileTree.vue` 递归显示目录结构，使用树形符号
- **表格视图**: `TableView.vue` 实现自适应列宽、流水屏动画、键盘导航

### 样式系统

- **CRT边框**: `border-radius` + `box-shadow` 创建复古显示器效果
- **表格布局**: `border-collapse: separate` + `border-spacing` 创建行间距
- **固定表头**: `position: sticky` 保持表头可见
- **滚动优化**: 隐藏滚动条但保持功能，防止页面抖动

## 许可证

MIT License

## 更新日志

### v1.0.0
- ✅ 初始版本发布
- ✅ Docker容器化部署
- ✅ CRT视觉效果
- ✅ 智能Markdown解析
- ✅ 自适应列宽算法
- ✅ 流水屏动画效果
- ✅ 完整键盘导航
- ✅ 自动保存机制