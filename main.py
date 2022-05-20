from fastapi import (
    FastAPI, Response, WebSocket, WebSocketDisconnect,
    Request
)
from typing import List

from pydantic import BaseModel
from fastapi.templating import Jinja2Templates

from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, mongo_client

from datetime import datetime

client = MongoClient('mongodb://root:rootpassword@127.0.0.1:27017')
db = client.chat_app



templates = Jinja2Templates(directory="templates")

app = FastAPI()

class RegisterValidator(BaseModel):
    username: str
    avatarURL: str

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# manager
class SocketManager:
    def __init__(self):
        self.active_connections: List[(WebSocket, str)] = []

    async def connect(self, websocket: WebSocket, user: str):
        await websocket.accept()
        self.active_connections.append((websocket, user))

    def disconnect(self, websocket: WebSocket, user: str):
        self.active_connections.remove((websocket, user))

    async def broadcast(self, data):
        for connection in self.active_connections:
            await connection[0].send_json(data)    

manager = SocketManager()

@app.websocket("/api/chat")
async def chat(websocket: WebSocket):
    sender = websocket.cookies.get("X-Authorization")
    if sender:
        await manager.connect(websocket, sender)
        response = {
            "sender": sender,
            "message": "got connected",
            "avatarURL": websocket.cookies.get("X-Avatar-URL")
        }
        await manager.broadcast(response)
        try:
            while True:
                data = await websocket.receive_json()
                data['date'] = datetime.now().timestamp()
                await manager.broadcast(data)
                db.chat_messages.insert_one(data)
        except WebSocketDisconnect:
            manager.disconnect(websocket, sender)
            response['message'] = "left"
            await manager.broadcast(response)

@app.get("/api/current_user")
def get_user(request: Request):
    return {"username": request.cookies.get("X-Authorization"),
            "avatarURL": request.cookies.get("X-Avatar-URL")
        }

@app.get('/api/messages')
def get_messages(request: Request):
    return list(db.chat_messages.find({}, {'_id':0}))

@app.post("/api/register")
def register_user(user: RegisterValidator, response: Response):
    response.set_cookie(key="X-Avatar-URL", value=user.avatarURL, httponly=True)
    response.set_cookie(key="X-Authorization", value=user.username, httponly=True)

@app.get("/")
def get_home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/chat")
def get_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})