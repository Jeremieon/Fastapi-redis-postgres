from pydantic import BaseModel
from typing import List


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    username: str
    password: str


class Login(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: int
    username: str
    email: str


class UserOut(UserBase):
    id: int
    username: str

    class Config:
        from_attributes = True


class UserList(BaseModel):
    users: List[UserOut]
