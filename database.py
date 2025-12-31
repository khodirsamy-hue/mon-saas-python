import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. On cherche l'adresse de la BDD dans les variables d'environnement (Render)
# Si on ne trouve rien (sur ton PC), on utilise le fichier sqlite local.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL:
    # Petit correctif car Render donne une adresse en "postgres://" 
    # mais SQLAlchemy veut du "postgresql://"
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # Configuration pour PostgreSQL (Prod)
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    # Configuration pour SQLite (Local)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()