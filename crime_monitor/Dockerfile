# Imagem base oficial do Python
FROM python:3.11-slim

# Evita criar arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1

# Garante que logs do Python apareçam no console
ENV PYTHONUNBUFFERED=1

# Diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para psycopg2 e sklearn
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements primeiro (melhor cache)
COPY requirements.txt .

# Instala dependências Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copia todo o projeto
COPY . .

# Expõe a porta do Flask
EXPOSE 5000

# Define variável padrão do Flask
ENV FLASK_APP=backend/app.py

# Comando para iniciar o servidor
CMD ["python", "backend/app.py"]