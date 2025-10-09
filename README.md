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

4\. Mude para a branch correta

```bash
git checkout henrique2
```

### 5. Acesse a pasta do sistema

```bash
cd crime_monitor
```

### 6. Crie o banco de dados

Execute o script SQL no PostgreSQL.

Substitua os valores entre < > conforme seu ambiente:

```bash
psql -U \-h \-p <5432> -W -f
```

💡 Exemplo:

```bash
psql -U postgres -h localhost -p 5432 -W -f backend/crime\_bd.sql
```

### 7. Crie o arquivo .env

Antes de rodar o sistema, crie um arquivo chamado .env dentro da pasta backend/ com as seguintes variáveis de ambiente:
```bash
DB_NAME=crimes
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
```

Essas variáveis serão usadas para configurar a conexão com o banco de dados PostgreSQL.

### 8. Execute o script de conexão com o banco

```bash
python backend/db.py
```

### 9. Inicie o servidor Flask

```bash

python backend/app.py
```

### 10. Acesse no navegador

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
│ │ │ └── maps/ 
│
└── README.md
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
