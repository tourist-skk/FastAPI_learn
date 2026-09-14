from fastapi import FastAPI
from pydantic import BaseModel,Field
from fastapi.responses import FileResponse


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}
    
@app.get("/file")
async def get_html():
    file_path = "./files/pencil.jpg"
    return FileResponse(file_path)