import psycopg2
import pandas as pd

# === 1. Conexão ao banco ===
conn = psycopg2.connect(
    dbname="crimes_RJ",
    user="postgres",
    password="crimes",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# === 2. Carregar CSV ===
df = pd.read_csv("backend/data/BaseDPEvolucaoMensalCisp.csv", sep=";", encoding="latin1")

# === 3. Limpar nomes das colunas ===
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

# === 4. Selecionar apenas as colunas que o banco espera e forçar tipo object ===
colunas_banco = [
    "cisp", "mes", "ano", "letalidade_violenta", "tentat_hom", "mcirc", "estupro", "lesao_corp_culposa",
    "roubo_veiculo", "estelionato", "apreensao_drogas", "trafico_drogas", "apf",
    "pessoas_desaparecidas", "encontro_cadaver", "registro_ocorrencias"
]
df_limpo = df[colunas_banco].astype(object)

# === 5. Substituir NaN por None para enviar NULL no PostgreSQL ===
df_limpo = df_limpo.where(pd.notnull(df_limpo), None)

# === 6. Inserir linha a linha, NULL será mantido ===
for idx, row in enumerate(df_limpo.itertuples(index=False, name=None), start=1):
    try:
        cursor.execute("""
            INSERT INTO crimes_RJ.dados_reais
            (cisp, mes, ano, letalidade_violenta, tentat_hom, mcirc, estupro, 
            lesao_corp_culposa, roubo_veiculo, estelionato, apreensao_drogas, 
            trafico_drogas, apf, pessoas_desaparecidas, encontro_cadaver, 
            registro_ocorrencias)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, row)
    except Exception as e:
        print(f"\nErro na linha {idx}: {row}")
        print(e)
        break

# === 7. Commit e fechamento ===
conn.commit()
cursor.close()
conn.close()

print("Dados inseridos com sucesso no banco crimes_RJ.dados_reais!")