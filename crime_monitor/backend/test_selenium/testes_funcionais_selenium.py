from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

BASE_URL = "http://127.0.0.1:5000"

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)


# --- LOGIN AUTOMÁTICO ---
def fazer_login(driver):
    print("Realizando login...")

    driver.get(BASE_URL + "/login")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "username"))
    )

    driver.find_element(By.NAME, "username").send_keys("elias")
    driver.find_element(By.NAME, "password").send_keys("123456")
    driver.find_element(By.NAME, "captcha").send_keys("TESTE")

    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    WebDriverWait(driver, 10).until(
        lambda d: (
            "/dashboard" in d.current_url
            or "/index" in d.current_url
            or d.current_url.endswith("/")
        )
    )

    print("Login realizado com sucesso!\n")


# ---------------- TESTE 1 ----------------
def test_acesso_pagina_inicial():
    driver = setup_driver()
    try:
        fazer_login(driver)

        driver.get(BASE_URL + "/")
        assert "Monitor RJ" in driver.title
        print("✔ Teste 1 OK: Página inicial acessada.\n")

    finally:
        driver.quit()


# ---------------- TESTE 2 ----------------
def test_fluxo_filtragem_dashboard():
    driver = setup_driver()
    try:
        fazer_login(driver)

        driver.get(BASE_URL + "/")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "data-inicio"))
        )

        driver.find_element(By.ID, "data-inicio").send_keys("2023-01-01")
        driver.find_element(By.ID, "data-fim").send_keys("2023-12-31")
        driver.find_element(By.ID, "municipio").send_keys("Rio de Janeiro")

        driver.find_element(By.ID, "btn-aplicar").click()

        kpi = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "total_letalidade"))
        )

        assert kpi.is_displayed(), "KPI não encontrado!"

        print("✔ Teste 2 OK: Dashboard filtrado e KPIs carregados.\n")

    finally:
        driver.quit()


# ---------------- TESTE 3 ----------------
def test_fluxo_geracao_previsao():
    driver = setup_driver()
    try:
        fazer_login(driver)

        driver.get(BASE_URL + "/previsao")

        wait = WebDriverWait(driver, 20)

        # Preencher formulário
        wait.until(EC.presence_of_element_located((By.ID, "cisp")))

        driver.find_element(By.ID, "cisp").send_keys("001")
        driver.find_element(By.ID, "mes").send_keys("8")
        driver.find_element(By.ID, "ano").send_keys("2025")
        driver.find_element(By.ID, "mcirc").send_keys("Rio de Janeiro")
        driver.find_element(By.ID, "tentat_hom").send_keys("15")
        driver.find_element(By.ID, "lesao_corp_culposa").send_keys("25")
        driver.find_element(By.ID, "roubo_veiculo").send_keys("120")
        driver.find_element(By.ID, "registro_ocorrencias").send_keys("850")

        driver.find_element(By.ID, "generate-btn").click()

        # ESPERAR a previsão aparecer (texto diferente de "-")
        print("Aguardando previsão...")
        previsao_element = wait.until(
            EC.presence_of_element_located((By.ID, "previsao_leitura"))
        )

        wait.until(lambda d: previsao_element.text.strip() != "-")

        previsao = previsao_element.text.strip()
        print("Previsão capturada:", previsao)

        assert previsao != "" and previsao != "-", "A previsão não foi gerada!"

        print("✔ Teste 3 OK: Previsão gerada.\n")

    finally:
        driver.quit()


# ---------------- TESTE 4 ----------------
def test_fluxo_filtro_vazio():
    driver = setup_driver()
    try:
        fazer_login(driver)

        driver.get(BASE_URL + "/previsao")

        wait = WebDriverWait(driver, 10)

        valor_inicial = wait.until(
            EC.presence_of_element_located((By.ID, "previsao_leitura"))
        ).text

        driver.find_element(By.ID, "generate-btn").click()

        time.sleep(1)

        valor_final = driver.find_element(By.ID, "previsao_leitura").text

        assert valor_inicial == valor_final, "Filtro vazio deveria manter o valor!"

        print("✔ Teste 4 OK: Filtro vazio não gerou previsão.\n")

    finally:
        driver.quit()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    test_acesso_pagina_inicial()
    test_fluxo_filtragem_dashboard()
    test_fluxo_geracao_previsao()
    test_fluxo_filtro_vazio()
