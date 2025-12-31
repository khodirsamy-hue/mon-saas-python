from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_premium = Column(Boolean, default=False)  # <--- La nouveauté !
    items = relationship("URLItem", back_populates="owner")

class URLItem(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    short_key = Column(String, unique=True, index=True)
    clicks = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="items")