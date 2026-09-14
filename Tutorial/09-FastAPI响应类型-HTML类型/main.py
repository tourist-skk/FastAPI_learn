from fastapi import FastAPI
from pydantic import BaseModel,Field
from fastapi.responses import HTMLResponse


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}
    
@app.get("/html", response_class=HTMLResponse)
async def get_html():
    return "<h1>Hello World</h1>"