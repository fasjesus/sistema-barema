# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model, UserMixin): 
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    # Define se é 'admin' (dev) ou 'coordenador' (colcic)
    cargo = db.Column(db.String(20), default='coordenador') 

class AnaliseBarema(db.Model):
    __tablename__ = 'analises'
    
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), nullable=False)
    nome_aluno = db.Column(db.String(100), nullable=False)
    email_aluno = db.Column(db.String(120), nullable=False) # E-mail sempre obrigatório
    whatsapp_aluno = db.Column(db.String(20), nullable=True) # WhatsApp opcional
    metodo_preferencial = db.Column(db.String(20), default='email') # 'email' ou 'whatsapp'
    caminho_pdf = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='Pendente')
    feedback = db.Column(db.Text, nullable=True)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
