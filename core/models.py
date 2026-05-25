# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from core.entities import CargoUsuario, Estudante, SolicitacaoAnalise, Usuario as UsuarioDominio

db = SQLAlchemy()

class Usuario(db.Model, UserMixin): 
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    # Define se é 'admin' (dev) ou 'coordenador' (colcic)
    cargo = db.Column(db.String(20), default=CargoUsuario.COORDENADOR)

    def eh_admin(self):
        return self.cargo == CargoUsuario.ADMIN

    def eh_coordenador(self):
        return self.cargo == CargoUsuario.COORDENADOR

    def to_domain(self):
        return UsuarioDominio(id=self.id, username=self.username, cargo=self.cargo)

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

    def to_domain(self):
        return SolicitacaoAnalise(
            id=self.id,
            estudante=Estudante(
                nome=self.nome_aluno,
                matricula=self.matricula,
                email=self.email_aluno,
            ),
            caminho_pdf=self.caminho_pdf,
            metodo_preferencial=self.metodo_preferencial,
            whatsapp_aluno=self.whatsapp_aluno,
            status=self.status,
            feedback=self.feedback,
        )

    def atualizar_por_entidade(self, solicitacao):
        self.nome_aluno = solicitacao.estudante.nome
        self.matricula = solicitacao.estudante.matricula
        self.email_aluno = solicitacao.estudante.email
        self.whatsapp_aluno = solicitacao.whatsapp_aluno
        self.metodo_preferencial = solicitacao.metodo_preferencial
        self.caminho_pdf = solicitacao.caminho_pdf
        self.status = solicitacao.status
        self.feedback = solicitacao.feedback
