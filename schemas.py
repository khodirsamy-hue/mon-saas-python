from pydantic import BaseModel
from typing import List, Optional

# --- URL SCHEMAS ---
class URLBase(BaseModel):
    url: str

class URLCreate(URLBase):
    custom_key: Optional[str] = None # Optionnel pour le frontend

class URLItem(URLBase):
    id: int
    short_key: str
    clicks: int
    owner_id: int

    class Config:
        orm_mode = True

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_premium: bool = False  # <--- VOICI LA LIGNE QUI MANQUAIT !
    items: List[URLItem] = []

    class Config:
        orm_mode = True

# --- TOKEN SCHEMAS ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class URLResponse(URLItem):
    pass