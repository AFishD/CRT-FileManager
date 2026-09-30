# V3.0 WebGL CRT 管线 — 真·桶形畸变

# CRT File Manager

一个拥有完整复古 CRT（阴极射线管）显示器效果的 Markdown 文件管理器 Web 应用。V3.0 起将 CRT 效果从 CSS 叠加层升级为 **WebGL2 实时渲染管线**:真实 DOM 被栅格化为纹理,经移植自 [Mega Bezel](https://github.com/HyperspaceMadness/Mega_Bezel)(RetroArch 着色器包)的 CRT-Pi 曲率公式渲染,实现真正的桶形畸变——扫描线、荫罩、暗角全部作用在弯曲后的坐标上,像真实曲面玻璃一样随屏幕弯曲。

## ✨ 功能特性

- 🖥️ **真·桶形畸变 (WebGL)**: Mega Bezel CRT-Pi 曲率 + 边缘补偿公式,四角削圆、边缘外鼓
- 📁 **智能文件扫描**: 递归扫描本地 Markdown 文件，自动解析表格数据
- ✅ **自动进度管理**: 智能检测并自动添加"进度"列，支持 `[ ]` / `[x]` 状态切换
- 🎮 **完整键盘导航**: 方向键移动、空格/回车切换、ESC 返回
- 🖱️ **鼠标交互**: 点击切换、悬停高亮、滚轮滚动(交互层与显示层分离,操作无损耗)
- 💾 **双模式保存**: 5 分钟自动保存 + 手动保存
- 🐳 **Docker 容器化**: 一键部署，多阶段构建
- 📊 **智能表格布局**: 自适应列宽、跑马灯溢出、分隔行识别
- 🌳 **树形文件浏览**: 递归目录结构，CRT 风格终端界面

## 🖥️ CRT 效果架构 (V3.0)

前端渲染分两层,由 `frontend/src/crt/` 驱动:

```
┌─ 真实 DOM (.crt-content, opacity:0)  ← 承接全部点击/滚轮/键盘,保持交互
│     ↓ MutationObserver / scroll / resize 触发 (节流)
├─ 栅格化 rasterizer.js                ← SVG foreignObject 拍成 canvas 纹理
│     · 字体按 unicode-range 内联为 data URL(CJK 字体按需,避免全量 3.5MB)
│     · 滚动容器平移补偿 + 粘性表头"占位符+绝对定位"钉住
│     · :hover/:focus 改写为类选择器,快照保留交互态
├─ WebGL2 渲染 renderer.js + shaders.js
│     · 桶形畸变: HSM_GetCrtPiCurvedCoord + HSM_Get2DCurvedCoord(边缘补偿)
│     · 圆角遮罩: HSM_GetCornerMask 距离场
│     · 扫描线/荫罩/暗角/辉光(bloom)/闪烁 全部在弯曲坐标上计算
│     · 荧光粉余晖: FBO 双缓冲,与上一帧取 max 实现亮点拖尾
└─ canvas (pointer-events:none)        ← 用户看到的画面
```

- **降级策略**: 无 WebGL2 或快照失败时自动回退为直接显示 DOM(无畸变)
- **浏览器要求**: Chromium / Firefox(Safari 的 foreignObject 渲染不完整,会走降级路径)
- **配置**: 全部参数在 `config/config.json` 的 `crt_effects` 段,新增 `barrel_x`/`barrel_y`(畸变强度)、`corner_radius`(圆角)、`persistence`(余晖拖影);旧字段全部兼容

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.10 + FastAPI 0.104.1 |
| **前端** | Vue.js 3.3.8 (Composition API) + Vite 5.0.0 |
| **部署** | Docker + Docker Compose (多阶段构建) |
| **数据模型** | Pydantic 2.5.0 |
| **字体** | Fusion Pixel 12px Monospaced (本地) |

## 🚀 快速开始

### Docker 部署（推荐）

1. 将 Markdown 文件放入 `./data` 目录
2. 构建并启动容器：

```bash
docker-compose up --build
```

3. 访问 `http://localhost`

容器特性：
- 多阶段构建（Node.js 前端构建 + Python 运行时）
- 国内镜像源加速（npm 淘宝源、pip 清华源、Debian 阿里云源）
- 健康检查机制 (`/health` 端点)
- 内存限制 4GB
- 自动重启策略

### 开发环境

#### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器会自动代理 `/api` 请求到 `http://localhost:8000`。

## 📄 Markdown 文件格式

支持标准 Markdown 表格格式：

### 带标题的表格

```markdown
### 一周目
| 武器名字   | 武器种类   | 武器收集地点  |
| ---------- | ---------- | ------------- |
| 诺威之长剑 | Long Sword | 第一章 第一节 |
| 艾丽丝之枪 | Spear      | 第一章 第三节 |
```

### 智能处理规则

- **自动添加进度列**: 如不存在则自动添加 `[ ]` / `[x]` 格式的进度列
- **分隔行识别**: 由 `-` 组成的行显示为空行，禁止交互
- **无标题处理**: 无标题时使用文件名作为标题

## ⌨️ 交互操作

| 按键 | 功能 |
|------|------|
| `↑` / `↓` | 上下移动选中行（自动跳过分隔行） |
| `←` / `→` | 切换表格（文件含多个表格时） |
| `空格` / `回车` | 切换当前行的完成状态 |
| `ESC` | 从表格视图返回文件树 |
| 鼠标点击 | 选中并切换行状态 |
| 鼠标滚轮 | 逐行滚动 |

## ⚙️ 配置文件

配置文件位于 `config/config.json`，通过 Docker volume 挂载到容器中。**修改后只需重启容器即可生效，无需重新构建镜像。**

支持 JSONC 格式（可使用 `//` 单行注释和 `/* */` 多行注释）。

```bash
# 修改配置后重启容器
docker-compose restart
```

### 配置项说明

```jsonc
{
  // CRT 显示器效果配置
  "crt_effects": {
    // 总开关 - 设为 false 可完全关闭所有CRT效果
    "enabled": true,

    // 桶形畸变 - 模拟CRT曲面玻璃
    "distortion": {
      "strength": 0.05,   // 畸变强度 (0-0.2)
      "zoom": 1.02        // 中心缩放比例 (1.0-1.1)
    },

    // 扫描线 - CRT逐行扫描的水平暗条纹
    "scanlines": {
      "opacity": 0.3,     // 不透明度 (0-1)
      "spacing": 2        // 间距 (px)
    },

    // 荫罩 - RGB荧光粉点阵
    "shadow_mask": {
      "enabled": true,    // 是否启用
      "opacity": 0.06     // 不透明度 (0-0.2)
    },

    // 暗角 - 中心亮、边缘暗
    "vignette": {
      "strength": 0.5     // 暗角强度 (0-1)
    },

    // 荧光粉余晖
    "glow": {
      "strength": "1px",                          // 光晕半径
      "color": "rgba(255, 255, 255, 0.35)"        // 光晕颜色
    },

    // 屏幕闪烁
    "flicker": {
      "enabled": true,    // 是否启用
      "intensity": 0.03   // 闪烁强度 (0-0.1)
    },

    // 模糊 - 荧光粉发光扩散
    "blur": {
      "strength": "0.3px" // 模糊半径
    },

    // 电源指示灯
    "power_led": {
      "enabled": true     // 是否显示
    }
  },

  // 颜色配置
  "colors": {
    "text_default": "#FFFFFF",                     // 默认文字颜色
    "text_completed": "#555555",                   // 已完成项颜色
    "text_dim": "#888888",                         // 次要文字颜色
    "highlight_bg": "rgba(255, 255, 255, 0.08)",   // 高亮行背景
    "accent": "#00ff41"                            // 强调色
  }
}
```

| 参数 | 说明 | 范围 |
|------|------|------|
| `crt_effects.enabled` | CRT效果总开关 | `true` / `false` |
| `distortion.strength` | 桶形畸变强度 | 0 - 0.2 |
| `distortion.zoom` | 中心缩放比例 | 1.0 - 1.1 |
| `scanlines.opacity` | 扫描线透明度 | 0 - 1 |
| `shadow_mask.opacity` | RGB荫罩透明度 | 0 - 0.2 |
| `vignette.strength` | 暗角效果强度 | 0 - 1 |
| `glow.strength` | 荧光粉余晖半径 | CSS单位 |
| `flicker.intensity` | 屏幕闪烁强度 | 0 - 0.1 |
| `blur.strength` | 模糊半径 | CSS单位 |
| `power_led.enabled` | 电源指示灯开关 | `true` / `false` |

## 📁 项目结构

```
CRT-FileManager/
├── docker-compose.yml          # Docker Compose 编排
├── config/
│   └── config.json             # CRT 效果配置 (JSONC, 挂载卷)
├── backend/
│   ├── Dockerfile              # 多阶段构建 (Node.js + Python)
│   ├── requirements.txt        # Python 依赖
│   └── app/
│       ├── main.py             # FastAPI 主入口 + /api/config 端点
│       ├── models/data.py      # Pydantic 数据模型
│       └── services/
│           ├── parser.py       # Markdown 解析服务
│           └── writer.py       # Markdown 写入服务
├── frontend/
│   ├── index.html              # 入口 HTML (CRT 启动画面)
│   ├── package.json            # 前端依赖
│   ├── vite.config.js          # Vite 配置
│   ├── fonts/                  # Fusion Pixel 像素字体
│   └── src/
│       ├── main.js             # Vue 入口
│       ├── App.vue             # 根组件
│       ├── assets/main.css     # 全局 CRT 样式 (CSS 变量)
│       └── components/
│           ├── CRTEffect.vue   # CRT 效果层 (核心)
│           ├── HeaderBar.vue   # 标题栏
│           ├── FileTree.vue    # 文件树
│           └── TableView.vue   # 表格视图
├── data/                       # Markdown 数据目录 (挂载卷)
└── reference/                  # CRT 效果参考文档
    └── apple2js/
        └── CRT_Barrel_Distortion_Analysis.md
```

## 📜 参考资料

- [apple2js](https://github.com/nicgirault/apple2js) - Apple II 网页模拟器，CRT 效果参考来源
- [screenEmu.js](https://github.com/nicgirault/apple2js/tree/master/submodules/apple2shader) - WebGL CRT 着色器实现

## License

MIT
