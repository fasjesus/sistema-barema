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
    caminho_pdf = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='Pendente')
    feedback = db.Column(db.Text, nullable=True)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)