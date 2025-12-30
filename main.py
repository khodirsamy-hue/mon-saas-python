import string
import random
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# On importe nos fichiers
import models, schemas, auth
from database import SessionLocal, engine

# Création des tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# 1. On configure le dossier où sont les pages web
templates = Jinja2Templates(directory="templates")

# 2. La Route d'accueil (Le Frontend)
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Configuration de la sécurité (Où récupérer le token ?)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- UTILITAIRES ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_short_key(length=5):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Fonction pour récupérer l'utilisateur connecté via son token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except auth.JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# --- ROUTES UTILISATEURS (AUTH) ---

# 1. Inscription
@app.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Vérifier si l'email existe déjà
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    # Hacher le mot de passe et créer l'utilisateur
    hashed_pwd = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_pwd)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# 2. Connexion (Login) -> Renvoie le Token
@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Chercher l'utilisateur
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # Vérifier le mot de passe
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Créer le token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- ROUTES URLS (LE PRODUIT) ---

# 3. Créer un lien (PROTÉGÉ : Il faut être connecté)
@app.post("/shorten", response_model=schemas.URLResponse)
def create_short_link(
    item: schemas.URLCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # <--- La sécurité est ici !
):
    key = generate_short_key()
    
    # On lie l'URL à l'utilisateur connecté (owner_id)
    new_url = models.URLItem(
    url=item.url,  # <--- On utilise 'url' ici aussi
    short_key=key, 
    owner_id=current_user.id
)
    
    db.add(new_url)
    db.commit()
    db.refresh(new_url)
    return new_url

# 4. Redirection (PUBLIC : Tout le monde peut cliquer)
@app.get("/{short_key}")
def redirect_to_site(short_key: str, db: Session = Depends(get_db)):
    url_item = db.query(models.URLItem).filter(models.URLItem.short_key == short_key).first()
    if url_item is None:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    
    url_item.clicks += 1
    db.commit()
    return RedirectResponse(url=url_item.url)

# 5. Voir MES liens (PROTÉGÉ)
@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# --- NOUVELLE ROUTE : SUPPRIMER UN LIEN ---
@app.delete("/links/{short_key}")
def delete_link(
    short_key: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. On cherche le lien
    link = db.query(models.URLItem).filter(
        models.URLItem.short_key == short_key,
        models.URLItem.owner_id == current_user.id # Sécurité : seul le propriétaire peut supprimer !
    ).first()
    
    if link is None:
        raise HTTPException(status_code=404, detail="Lien introuvable ou vous n'êtes pas le propriétaire")
    
    # 2. On supprime
    db.delete(link)
    db.commit()
    return {"message": "Lien supprimé avec succès"}