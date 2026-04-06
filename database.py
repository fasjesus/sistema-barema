import sqlite3
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            nome_aluno TEXT NOT NULL,
            caminho_pdf TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente',
            feedback TEXT,
            data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de Usuários (Apenas para o Coordenador)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Verifica se já existe algum coordenador, se não, cria o padrão
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        user_coord = "admin_colcic"
        pass_coord = generate_password_hash("colcic2026")
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user_coord, pass_coord))
    
    conn.commit()
    conn.close()