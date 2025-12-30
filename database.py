from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. On définit le nom de la base de données (ce sera un simple fichier)
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# 2. On crée le "moteur" de connexion
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. On crée la "session" (l'outil pour envoyer des commandes)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. On crée la base pour nos futurs modèles (tables)
Base = declarative_base()