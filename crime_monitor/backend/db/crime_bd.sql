CREATE DATABASE crimes;
 
\c crimes
 
CREATE TABLE IF NOT EXISTS dados_previstos
(
    prev_id bigserial NOT NULL,
    cisp smallint NOT NULL,
    mcirc bigint NOT NULL,
    mes smallint NOT NULL,
    ano integer NOT NULL,
    letalidade_violenta integer,
    tentat_hom integer,
    estupro integer,
    lesao_corp_culposa integer,
    roubo_veiculo integer,
    estelionato integer,
    apreensao_drogas integer,
    trafico_drogas integer,
    apf integer,
    pessoas_desaparecidas integer,
    encontro_cadaver integer,
    registro_ocorrencias integer,
    CONSTRAINT dados_previstos_pkey PRIMARY KEY (prev_id)
);
 
CREATE TABLE IF NOT EXISTS dados_reais
(
    real_id bigserial NOT NULL,
    cisp smallint NOT NULL,
    mcirc bigint NOT NULL,
    mes smallint NOT NULL,
    ano integer NOT NULL,
    letalidade_violenta integer,
    tentat_hom integer,
    estupro integer,
    lesao_corp_culposa integer,
    roubo_veiculo integer,
    estelionato integer,
    apreensao_drogas integer,
    trafico_drogas integer,
    apf integer,
    pessoas_desaparecidas integer,
    encontro_cadaver integer,
    registro_ocorrencias integer,
    CONSTRAINT dados_reais_pkey PRIMARY KEY (real_id)
);
 
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);
 
INSERT INTO users (nome, email, username, password)
VALUES ('Elias', 'eliasasd321@gmail.com', 'elias', '123456');