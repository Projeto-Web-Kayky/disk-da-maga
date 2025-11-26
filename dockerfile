# Use a versão do Python do seu projeto
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia o arquivo de requirements
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto
COPY . .

# Expõe a porta que o aplicativo vai usar
EXPOSE 8000

# Comando para iniciar o aplicativo
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

**Ajuste a versão do Python** (`python:3.11-slim`) para a versão que você está usando no seu projeto.

## 4. Criar arquivo .dockerignore

Crie um arquivo `.dockerignore` na raiz do projeto para evitar copiar arquivos desnecessários:
```
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.Python
db.sqlite3
.git
.gitignore
.env
*.log