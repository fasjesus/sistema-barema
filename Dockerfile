# 1. Usa uma imagem oficial do Python super leve
FROM python:3.10-slim

# 2. Instala as dependências do sistema operacional (O Tesseract OCR em português)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 3. Define a pasta de trabalho no servidor
WORKDIR /app

# 4. Copia os arquivos de dependência e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o resto do código do seu projeto
COPY . .

# 6. A TÁTICA 1: Executa o seed.py e, se der certo (&&), liga o servidor Gunicorn
# Nota: O Render fornece a porta automaticamente através da variável $PORT
CMD sh -c "python seed.py && gunicorn app:app --bind 0.0.0.0:$PORT"