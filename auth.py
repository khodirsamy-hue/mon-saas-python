from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# --- CONFIGURATION SECRÈTE ---
# Dans la vraie vie, on cache ça dans des variables d'environnement !
SECRET_KEY = "ma_super_cle_secrete_pour_le_dev"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# L'outil qui va hacher les mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fonction 1 : Vérifier si le mot de passe est bon
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Fonction 2 : Transformer le mot de passe en hash (cryptage)
def get_password_hash(password):
    return pwd_context.hash(password)

# Fonction 3 : Créer le badge d'accès (Token JWT)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt