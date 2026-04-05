# 🧠 IA_PI — Sistema de Previsão de Letalidade Violenta

Este projeto tem como objetivo realizar análises e previsões de letalidade violenta no estado do Rio de Janeiro, utilizando **Python**, **Flask**, e **PostgreSQL**.

---

## 🚀 Como rodar o projeto

Siga as etapas abaixo para executar o projeto localmente.

### 1. Clone o repositório

```bash
git clone https://github.com/gabrielamaiia01/IA\_PI.git
```

### 2. Acesse o diretório do projeto

```bash
cd IA\_PI
```

### 3. Abra o projeto no VS Code

```bash
code .
```

### 4. Acesse a pasta do sistema

```bash
cd crime_monitor
```

### 5. Crie um ambiente virtual

```bash
python -m venv venv
```

### 6. Ative o ambiente virtual

```bash
venv\Scripts\activate
```

### 7. Acesse o PSQL

Execute no terminal (com o psql instalado):

```bash
psql -U <usuario>
```

Substitua <usuario> pelo nome do seu usuário no PostgreSQL. Exemplo:

```bash
psql -U postgres
```

### 8. Crie o banco de dados

Execute o script SQL no PostgreSQL.

Substitua os valores entre < > conforme seu ambiente:

```bash
psql -U \-h \-p <5432> -W -f
```

💡 Exemplo:

```bash
psql -U postgres -h localhost -p 5432 -W -f backend/db/crime_bd.sql
```

### 9. Crie o arquivo .env

Antes de rodar o sistema, crie um arquivo chamado .env dentro da pasta backend/ com as seguintes variáveis de ambiente:
```bash
DB_NAME=crimes
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
OPENROUTER_API_KEY=sua_chave_de_api
IP_OR_HOST=127.0.0.1
FLASK_SECRET_KEY=chave_super_secreta
```

Essas variáveis serão usadas para configurar a conexão com o banco de dados PostgreSQL.

### 10. Execute o script de conexão com o banco

```bash
python backend/db.py
```

### 11. Inicie o servidor Flask

```bash

python backend/app.py
```

### 12. Acesse no navegador

Abra o endereço abaixo para visualizar o sistema:

http://127.0.0.1:5000

### 🧩 Estrutura do projeto

```bash
IA_PI/
│
├── crime_monitor/
│ ├── backend/
│ │ ├── app.py # Aplicação Flask
│ │ ├── db.py # Conexão com o banco
│ │ └── crime_bd.sql # Script de criação do banco
│ └── frontend/ # Interface web
│ │ └── pages/ 
│ │ │ ├── agrupamento.html 
│ │ │ ├── index.html 
│ │ │ └── previsao.html 
│ │ └── static/ 
│ │ │ └── css/ 
│ │ │ │ └── style.css
│ │ │ └── img/ 
│ │ │ └── js/ 
│ │ │ │ ├── agrupamento.js
│ │ │ │ ├── index.js
│ │ │ │ └── previsao.js
│
└── README.md
```

# 🧪 Como executar os testes

O projeto possui dois tipos de testes:

- **Testes unitários do frontend (Jest)**
- **Testes funcionais do backend (Selenium)**

---

## ✔️ 1. Testes Unitários (Jest)

Certifique-se de estar dentro da pasta `crime_monitor` antes de rodar os comandos.

### ▶️ Instale as dependências (se ainda não instalou)

```bash
npm install
```

### ▶️ Execute cada teste separadamente
**🔹Teste da página de Previsão**
```bash
npx jest frontend/static/js/tests/testes_unitarios_jest_previsao.test.js
```

**🔹 Teste da página de Dashboard**
```bash
npx jest frontend/static/js/tests/testes_unitarios_jest_dashboard.test.js
```

**🔹 Teste da página de Agrupamento**

```bash
npx jest frontend/static/js/tests/testes_unitarios_jest_agrupamento.test.js
```

## ✔️ 2. Testes Funcionais (Selenium)
⚠️ Atenção: Antes de rodar os testes Selenium, o servidor Flask deve estar em execução.


### ▶️ 1. Adicione no .env esta linha:

```bash
TEST_MODE="1"
```

Isso vai fazer com que o captcha seja ignorado no login, ou seja, o usuário pode colocar um valor errado no catpcha e mesmo assim vai passar.

### ▶️ 2. Inicie o backend em um terminal:

```bash
python backend/app.py
```

### ▶️ 3. Em outro terminal, execute o teste Selenium:

```bash
python backend/test_selenium/testes_funcionais_selenium.py
```

O Selenium abrirá o navegador automaticamente e realizará os testes acessando:

```bash
http://127.0.0.1:5000
```

### 🛠️ Tecnologias utilizadas
- **Python 3**
- **Flask**
- **PostgreSQL**
- **Pandas / NumPy / Scikit-Learn**
- **HTML / CSS / JavaScript**

### 🧑‍💻 Equipe

- @gabrielamaiia01
- @HenriqueSilvaXavier
- @rafaelts007
- @FlaviaPaloma
- @YLASP
- @Elias969 

### ⚙️ Observações

Certifique-se de ter o PostgreSQL instalado e rodando.

O banco e as tabelas são criados a partir do arquivo crime\_bd.sql.

Use um ambiente virtual (venv) se desejar isolar as dependências.
