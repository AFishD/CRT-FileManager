import os
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from .services import scan_directory, write_multiple_updates
from .models import SaveRequest, SaveResponse

# 创建FastAPI应用
app = FastAPI(
    title="CRT Collectibles Tracker API",
    description="Markdown游戏收集品追踪器API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置静态文件目录（在生产环境中使用）
# 在Docker容器中，前端构建产物在 /app/frontend/dist
STATIC_DIR = "/app/frontend/dist"
print(f"=" * 60)
print(f"DEBUG: 静态文件目录路径: {STATIC_DIR}")
print(f"DEBUG: 静态文件目录是否存在: {os.path.exists(STATIC_DIR)}")
print(f"=" * 60)

if os.path.exists(STATIC_DIR):
    print(f"DEBUG: 静态文件目录内容: {os.listdir(STATIC_DIR)}")
    # 检查dist目录下的具体内容
    for item in os.listdir(STATIC_DIR):
        item_path = os.path.join(STATIC_DIR, item)
        if os.path.isdir(item_path):
            print(f"DEBUG: 目录: {item}/")
            # 列出子目录内容
            try:
                sub_items = os.listdir(item_path)
                for sub_item in sub_items[:5]:  # 只显示前5个，避免日志过多
                    print(f"DEBUG:   - {sub_item}")
                if len(sub_items) > 5:
                    print(f"DEBUG:   ... 还有 {len(sub_items) - 5} 个文件")
            except Exception as e:
                print(f"DEBUG:   无法读取子目录内容: {e}")
        else:
            print(f"DEBUG: 文件: {item} (大小: {os.path.getsize(item_path)} bytes)")
else:
    print(f"警告: 静态文件目录不存在: {STATIC_DIR}")
    print(f"DEBUG: 当前工作目录: {os.getcwd()}")
    print(f"DEBUG: 工作目录内容: {os.listdir(os.getcwd())}")

# 数据目录 - 使用绝对路径，确保在Docker容器中正确访问
DATA_DIR = "/app/data"
print(f"DEBUG: 数据目录路径: {DATA_DIR}")
print(f"DEBUG: 数据目录是否存在: {os.path.exists(DATA_DIR)}")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)
print(f"DEBUG: 数据目录确保存在: {os.path.exists(DATA_DIR)}")

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"DEBUG: 收到请求: {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    print(f"DEBUG: 响应: {response.status_code} | 处理时间: {process_time:.3f}s")
    return response

# 先定义API路由（在挂载静态文件之前）
@app.get("/api/structure")
async def get_structure():
    """
    获取所有Markdown文件的结构化数据
    """
    print(f"DEBUG: API请求 /api/structure")
    try:
        results = scan_directory(DATA_DIR)
        print(f"DEBUG: 扫描完成，找到 {len(results)} 个文件")
        return {"files": results}
    except Exception as e:
        print(f"ERROR: 扫描目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"扫描目录失败: {str(e)}")

@app.get("/api/file-tree")
async def get_file_tree():
    """
    获取文件树结构，用于文件管理器
    """
    print(f"DEBUG: API请求 /api/file-tree")
    try:
        tree = build_file_tree(DATA_DIR)
        print(f"DEBUG: 构建文件树完成")
        return {"tree": tree}
    except Exception as e:
        print(f"ERROR: 构建文件树失败: {e}")
        raise HTTPException(status_code=500, detail=f"构建文件树失败: {str(e)}")

@app.post("/api/save", response_model=SaveResponse)
async def save_changes(save_request: SaveRequest):
    """
    保存更改到Markdown文件
    """
    print(f"DEBUG: API请求 /api/save，更新 {len(save_request.updates)} 个表格")
    try:
        results = write_multiple_updates(save_request.updates, DATA_DIR)
        
        if results['success']:
            print(f"INFO: 保存成功: {len(results['updated_files'])} 个文件已更新")
            for file_path in results['updated_files']:
                print(f"INFO:   - {file_path}")
            return SaveResponse(success=True, message="保存成功")
        else:
            error_msg = "保存失败:\n" + "\n".join([
                f"  {err['file']}: {err['error']}"
                for err in results['errors']
            ])
            print(f"ERROR: {error_msg}")
            return SaveResponse(success=False, message=error_msg)
            
    except Exception as e:
        error_msg = f"保存失败: {str(e)}"
        print(f"ERROR: {error_msg}")
        return SaveResponse(success=False, message=error_msg)

# 定义其他API路由
@app.get("/health")
async def health_check():
    """
    健康检查接口
    """
    print(f"DEBUG: 健康检查请求 /health")
    return {"status": "healthy", "service": "CRT Collectibles Tracker API"}

# 删除重复的静态文件挂载，只保留一次
# 移除第33-34行的 /app 挂载，只保留根路径挂载

# 最后挂载静态文件服务（只挂载一次）
if os.path.exists(STATIC_DIR):
    print(f"DEBUG: 准备挂载静态文件服务到根路径")
    print(f"DEBUG: StaticFiles 配置: directory={STATIC_DIR}, html=True")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    print("DEBUG: 静态文件服务已挂载到根路径 /")
    print(f"=" * 60)
else:
    print(f"警告: 静态文件目录不存在: {STATIC_DIR}")
    print(f"DEBUG: 当前工作目录: {os.getcwd()}")
    print(f"DEBUG: 工作目录内容: {os.listdir(os.getcwd())}")
    print(f"=" * 60)
    
    # 如果静态文件不存在，定义根路径路由
    @app.get("/")
    async def read_root():
        return {"message": "前端页面未构建，请运行 npm run build", "error": "STATIC_DIR_NOT_FOUND"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)