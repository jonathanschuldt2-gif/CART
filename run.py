import uvicorn
from app import config as cfg

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=cfg.HOST, port=cfg.PORT, reload=False)
