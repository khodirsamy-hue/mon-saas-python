from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_premium = Column(Boolean, default=False)
    items = relationship("URLItem", back_populates="owner")

class URLItem(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    short_key = Column(String, unique=True, index=True)
    clicks = Column(Integer, default=0) # On garde le total pour l'affichage rapide
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="items")
    
    # NOUVEAU : Le lien vers l'historique des clics
    click_history = relationship("Click", back_populates="link", cascade="all, delete-orphan")

class Click(Base):
    __tablename__ = "clicks"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow) # L'heure du clic
    link_id = Column(Integer, ForeignKey("urls.id"))
    link = relationship("URLItem", back_populates="click_history")