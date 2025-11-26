 
import psycopg2
import os
import pandas as pd
from dotenv import load_dotenv
from urllib.parse import urlparse
 
# === 1. Carregar variáveis do arquivo .env ===
load_dotenv()
 
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
 
def get_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    
    # fallback local
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
 
def load_csv():
    """Carrega o CSV de forma segura"""
    # Caminho absoluto relativo a este arquivo
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "data", "BaseDPEvolucaoMensalCisp.csv")
 
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Arquivo CSV não encontrado em: {csv_path}")
 
    df = pd.read_csv(csv_path, sep=";", encoding="latin1")
 
    # Limpar nomes das colunas
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
 
    # Selecionar colunas esperadas
    colunas_banco = [
        "cisp", "mcirc", "mes", "ano",
        "letalidade_violenta", "tentat_hom", "estupro",
        "lesao_corp_culposa", "roubo_veiculo", "estelionato",
        "apreensao_drogas", "trafico_drogas", "apf",
        "pessoas_desaparecidas", "encontro_cadaver",
        "registro_ocorrencias"
    ]
 
    df_limpo = df[colunas_banco].astype(object)
    df_limpo = df_limpo.where(pd.notnull(df_limpo), None)  # substituir NaN por None
 
    return df_limpo
 
 
def insert_data(df):
    """Insere os dados no banco"""
    conn = get_connection()
    cursor = conn.cursor()
 
    for idx, row in enumerate(df.itertuples(index=False, name=None), start=1):
        try:
            cursor.execute("""
                INSERT INTO public.dados_reais
                (cisp, mcirc, mes, ano, letalidade_violenta, tentat_hom, estupro,
                lesao_corp_culposa, roubo_veiculo, estelionato, apreensao_drogas,
                trafico_drogas, apf, pessoas_desaparecidas, encontro_cadaver,
                registro_ocorrencias)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, row)
        except Exception as e:
            print(f"\nErro na linha {idx}: {row}")
            print(e)
            break
 
    conn.commit()
    cursor.close()
    conn.close()
    print("Dados inseridos com sucesso no banco crimes_RJ.dados_reais!")
 
 
# === Uso ===
# Só executa se rodar este script diretamente
if __name__ == "__main__":
    df = load_csv()
    insert_data(df)
 