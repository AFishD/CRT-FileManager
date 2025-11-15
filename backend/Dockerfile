# 阶段1: 构建前端
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端依赖文件
COPY frontend/package*.json ./
# 使用国内npm镜像源加速安装
RUN npm config set registry https://registry.npmmirror.com && \
    npm install

# 复制前端源代码
COPY frontend/ ./

# 构建前端并显示详细构建信息
RUN echo "=== 开始构建前端 ===" && \
    echo "当前目录:" && \
    pwd && \
    echo "目录内容:" && \
    ls -la && \
    echo "运行npm run build..." && \
    npm run build && \
    echo "=== 构建完成 ===" && \
    echo "检查构建产物:" && \
    echo "dist目录是否存在:" && \
    ls -la dist/ && \
    echo "dist目录完整内容:" && \
    find dist -type f -exec ls -la {} \; && \
    echo "=== 构建产物检查完成 ==="

# 阶段2: 构建最终镜像
FROM python:3.10-slim

WORKDIR /app

# 配置Debian国内镜像源（阿里云）
RUN echo "配置Debian镜像源..." && \
    # 备份原始sources.list（如果存在）
    if [ -f /etc/apt/sources.list ]; then cp /etc/apt/sources.list /etc/apt/sources.list.backup; fi && \
    # 创建新的sources.list文件
    echo "deb http://mirrors.aliyun.com/debian trixie main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian trixie-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security trixie-security main contrib non-free" >> /etc/apt/sources.list && \
    echo "镜像源配置完成"

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制Python依赖
COPY backend/requirements.txt ./

# 安装Python依赖（使用国内镜像源加速）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制后端代码
COPY backend/app ./app

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 创建data目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 80

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]