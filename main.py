import string
import random
import os
import stripe
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr, BaseModel
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
    current_user: models.User = Depends(get_current_user)
):
    # 1. Vérification Alias Personnalisé (Le Vigile)
    if item.custom_key:
        # Si l'utilisateur n'est PAS premium, on bloque !
        if not current_user.is_premium:
            raise HTTPException(
                status_code=403, 
                detail="Les alias personnalisés sont réservés aux membres PREMIUM (4.99€/mois)."
            )
        
        # Si c'est un membre premium, on vérifie si le mot est libre
        existing_link = db.query(models.URLItem).filter(models.URLItem.short_key == item.custom_key).first()
        if existing_link:
            raise HTTPException(status_code=400, detail="Désolé, cet alias est déjà pris !")
        
        key = item.custom_key
    
    else:
        # 2. Pas d'alias demandé -> On génère une clé aléatoire (Gratuit)
        key = generate_short_key()
    
    # 3. Création du lien dans la base
    new_url = models.URLItem(
        url=item.url, 
        short_key=key, 
        owner_id=current_user.id
    )
    
    db.add(new_url)
    db.commit()
    db.refresh(new_url)
    return new_url

# --- CONFIGURATION STRIPE ---
stripe.api_key = os.getenv("STRIPE_API_KEY")

# 1. CRÉATION DU PAIEMENT (Avec l'identité de l'utilisateur)
@app.post("/create-checkout-session")
def create_checkout_session(current_user: models.User = Depends(get_current_user)):
    # ⚠️ IMPORTANT : Vérifie que c'est bien l'adresse exacte de ton site Render ci-dessous !
    domain_url = "https://pyshort-eds1.onrender.com" 
    
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        # C'est ici qu'on colle l'étiquette avec l'ID du client pour le retrouver après
        client_reference_id=str(current_user.id), 
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': 'Abonnement PyShort PRO'},
                'unit_amount': 499,
            },
            'quantity': 1,
        }],
        mode='payment',
        # On redirige vers la route /success qu'on crée juste en dessous
        success_url=domain_url + '/success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=domain_url,
    )
    return {"checkout_url": checkout_session.url}

# 2. LA VALIDATION (Le tampon "Payé")
@app.get("/success")
def success_payment(request: Request, session_id: str, db: Session = Depends(get_db)):
    # On demande à Stripe : "Alors, c'est payé ?"
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except:
        return templates.TemplateResponse("index.html", {"request": request}) # En cas d'erreur, retour accueil
    
    if session.payment_status == 'paid':
        # On lit l'étiquette pour savoir QUI a payé
        user_id = session.client_reference_id
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if user:
            # On active le mode Premium
            user.is_premium = True
            db.commit()
            # C'est ici qu'on renvoie la belle page HTML 🎉
            return templates.TemplateResponse("success.html", {"request": request})
    
    return {"error": "Paiement non validé."}

# 4. Redirection (PUBLIC : Tout le monde peut cliquer)
@app.get("/{short_key}")
def redirect_to_site(short_key: str, db: Session = Depends(get_db)):
    url_item = db.query(models.URLItem).filter(models.URLItem.short_key == short_key).first()
    if url_item is None:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    
    # 1. On met à jour le compteur total
    url_item.clicks += 1
    
    # 2. NOUVEAU : On enregistre l'événement "Clic" avec l'heure actuelle
    new_click = models.Click(link_id=url_item.id)
    db.add(new_click)
    
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

# --- CHEAT CODE (A SUPPRIMER PLUS TARD) ---
@app.get("/admin/upgrade_me")
def upgrade_me(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # On passe l'utilisateur en Premium
    current_user.is_premium = True
    db.commit()
    return {"message": "Félicitations ! Vous êtes maintenant membre VIP (Premium) gratuitement."}

# --- CONFIGURATION EMAIL ---
# On récupère les infos secrètes depuis les variables d'environnement
mail_conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_USERNAME"),
    MAIL_PORT = 465,  # <--- On change le port
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = False, # <--- On désactive le démarrage progressif
    MAIL_SSL_TLS = True,   # <--- On active le SSL direct
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# --- ROUTE MOT DE PASSE OUBLIÉ ---

class EmailSchema(BaseModel):
    email: EmailStr

@app.post("/forgot-password")
async def forgot_password(email_data: EmailSchema, db: Session = Depends(get_db)):
    print(f"🔍 Recherche de l'utilisateur : {email_data.email}") # LOG 1

    # 1. On vérifie si l'email existe
    user = db.query(models.User).filter(models.User.email == email_data.email).first()
    
    if not user:
        print("❌ UTILISATEUR INTROUVABLE DANS LA BDD") # LOG 2
        return {"message": "Si cet email existe, un lien a été envoyé."}

    print(f"✅ Utilisateur trouvé (ID: {user.id}). Préparation de l'email...") # LOG 3

    # 2. On crée un token de réinitialisation
    access_token_expires = timedelta(minutes=15)
    reset_token = auth.create_access_token(
        data={"sub": user.email, "type": "reset"},
        expires_delta=access_token_expires
    )

    # 3. On prépare l'email
    reset_link = f"https://pyshort-eds1.onrender.com/reset-password?token={reset_token}"
    
    html = f"""
    <h3>Réinitialisation de mot de passe</h3>
    <p>Cliquez sur le lien ci-dessous pour changer votre mot de passe :</p>
    <a href="{reset_link}">Changer mon mot de passe</a>
    """

    message = MessageSchema(
        subject="PyShort - Reset Password",
        recipients=[user.email],
        body=html,
        subtype=MessageType.html
    )

    # 4. On envoie
    try:
        fm = FastMail(mail_conf)
        await fm.send_message(message)
        print("🚀 EMAIL ENVOYÉ AU SERVEUR GMAIL AVEC SUCCÈS") # LOG 4
    except Exception as e:
        print(f"💥 ERREUR CRITIQUE PENDANT L'ENVOI : {e}") # LOG 5
    
    return {"message": "Email envoyé !"}
    

    # 3. On prépare l'email
    reset_link = f"https://pyshort-eds1.onrender.com/reset-password?token={reset_token}"
    
    html = f"""
    <h3>Réinitialisation de mot de passe</h3>
    <p>Cliquez sur le lien ci-dessous pour changer votre mot de passe (valable 15min) :</p>
    <a href="{reset_link}">Changer mon mot de passe</a>
    <br>
    <p>Si vous n'avez rien demandé, ignorez cet email.</p>
    """

    message = MessageSchema(
        subject="PyShort - Réinitialisation mot de passe",
        recipients=[user.email],
        body=html,
        subtype=MessageType.html
    )

    # 4. On envoie
    fm = FastMail(mail_conf)
    await fm.send_message(message)
    
    return {"message": "Email envoyé !"}

# --- ROUTE POUR AFFICHER LA PAGE DE CHANGEMENT DE MDP ---
@app.get("/reset-password")
def reset_password_page(token: str, request: Request):
    # On renvoie une page HTML simple pour saisir le nouveau mot de passe
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

# --- ROUTE POUR VALIDER LE CHANGEMENT ---
class NewPasswordSchema(BaseModel):
    token: str
    new_password: str

@app.post("/reset-password-confirm")
def reset_password_confirm(data: NewPasswordSchema, db: Session = Depends(get_db)):
    # 1. On décode le token
    try:
        payload = auth.jwt.decode(data.token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if email is None or token_type != "reset":
            raise HTTPException(status_code=400, detail="Token invalide")
            
    except auth.JWTError:
        raise HTTPException(status_code=400, detail="Token expiré ou invalide")

    # 2. On change le mot de passe
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.hashed_password = auth.get_password_hash(data.new_password)
    db.commit()

    return {"message": "Mot de passe modifié avec succès ! Connectez-vous."}