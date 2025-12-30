from pydantic import BaseModel
from typing import List, Optional

# --- SCHÉMAS POUR LES TOKENS (Le badge d'accès) ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

# --- SCHÉMAS POUR LES URLS ---
class URLBase(BaseModel):
    url: str

class URLCreate(URLBase):
    custom_key: str | None = None  # Nouveau : L'utilisateur peut proposer son mot (ou rien)

class URLResponse(URLBase):
    short_key: str
    clicks: int
    
    class Config:
        from_attributes = True

# --- SCHÉMAS POUR LES UTILISATEURS ---
class UserBase(BaseModel):
    email: str

# Ce que l'utilisateur envoie pour s'inscrire (avec mot de passe)
class UserCreate(UserBase):
    password: str

# Ce que l'API renvoie (JAMAIS le mot de passe !)
class UserResponse(UserBase):
    id: int
    items: List[URLResponse] = []

    class Config:
        from_attributes = True