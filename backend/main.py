from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
# 注意：这里没有 "."，直接引用同级文件
from engine import CausalDiscoveryEngine 

app = FastAPI()

# 允许跨域，这样前端 Next.js 才能调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，开发环境图方便
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化引擎
engine = CausalDiscoveryEngine()

class EventRequest(BaseModel):
    event: str

@app.post("/api/analyze")
async def analyze_event(request: EventRequest):
    print(f"收到请求: {request.event}") # 打印一下，方便调试
    try:
        # 调用 engine.py 里的逻辑
        result = engine.analyze_event(request.event)
        return result
    except Exception as e:
        print(f"处理出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"status": "Domino-Agent Backend is Running!"}