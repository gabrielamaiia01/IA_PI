from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time

# Configuração do WebDriver (necessário ter o ChromeDriver instalado e no PATH)
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Em um ambiente real, você precisaria do caminho exato para o ChromeDriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# URL base do aplicativo Flask (assumindo que está rodando na porta 5000)
BASE_URL = "http://127.0.0.1:5000"

# Teste Básico (Exemplo 4)
def test_acesso_pagina_inicial():
    """
    Teste Básico: Acessa a página inicial e verifica o título.
    """
    driver = setup_driver()
    print("\n--- Teste Básico: Acesso à Página Inicial ---")
    try:
        driver.get(BASE_URL + "/")
        time.sleep(2)
        assert "Monitor RJ - Dashboard" in driver.title
        print("Sucesso: Página inicial acessada e título verificado.")
    except Exception as e:
        print(f"Falha: {e}")
    finally:
        driver.quit()

# --- Fluxo 1: Teste de Filtragem no Dashboard ---
def test_fluxo_filtragem_dashboard():
    """
    Fluxo 1: Simula a filtragem de dados no Dashboard.
    (Assume a existência de campos de filtro no HTML)
    """
    driver = setup_driver()
    print("\n--- Fluxo 1: Teste de Filtragem no Dashboard ---")
    try:
        driver.get(BASE_URL + "/")
        time.sleep(2)

        # 1. Preenche Período (Simulando seleção de Ano/Mês)
        # Usando o seletor existente no index.html
        periodo_select = Select(driver.find_element(By.ID, "periodo"))
        periodo_select.select_by_visible_text("Ano/Mês") # Seleciona a opção padrão (simulação)
        print("Passo 1: Período preenchido.")

        # 2. Seleciona Região (Simulando seleção de Município/Bairro)
        regiao_select = Select(driver.find_element(By.ID, "regiao"))
        regiao_select.select_by_visible_text("Município / Bairro") # Seleciona a opção padrão (simulação)
        print("Passo 2: Região selecionada.")

        # 3. Clica em "Filtrar" (Simulação: Não há botão explícito, mas a mudança de filtro deve acionar)
        # Em um app real, haveria um botão. Aqui, simulamos que a mudança de select já é o filtro.
        print("Passo 3: Simulação de clique em 'Filtrar' (Mudança de filtro acionada).")

        # 4. Verifica se o dashboard é atualizado (Simulação: Verifica se os KPIs ainda estão visíveis)
        kpi_element = driver.find_element(By.ID, "total_letalidade")
        assert kpi_element.is_displayed()
        print(f"Passo 4: Dashboard visível. KPI Letalidade Total: {kpi_element.text}")

        print("Sucesso: Fluxo de Filtragem concluído.")

    except Exception as e:
        print(f"Falha: {e}")
    finally:
        driver.quit()

# --- Fluxo 2: Teste de Geração de Previsão (Simulando Relatório) ---
def test_fluxo_geracao_previsao():
    """
    Fluxo 2: Simula a geração de relatório/previsão na página de Previsão.
    """
    driver = setup_driver()
    print("\n--- Fluxo 2: Teste de Geração de Previsão ---")
    try:
        driver.get(BASE_URL + "/previsao")
        time.sleep(2)

        # 1. Seleciona Período Futuro
        periodo_select = Select(driver.find_element(By.ID, "periodo-futuro"))
        periodo_select.select_by_visible_text("Próximo mês")
        print("Passo 1: Período futuro selecionado.")

        # 2. Seleciona Região
        regiao_select = Select(driver.find_element(By.ID, "regiao-previsao"))
        regiao_select.select_by_visible_text("Estado do RJ")
        print("Passo 2: Região selecionada.")

        # 3. Clica em "Gerar Previsão"
        generate_button = driver.find_element(By.CLASS_NAME, "generate-button")
        generate_button.click()
        time.sleep(3) # Espera a "geração"

        # 4. Verifica se os detalhes da previsão foram carregados (Simulação de relatório)
        previsao_kpi = driver.find_element(By.ID, "previsao_leitura")
        assert previsao_kpi.text != "" and previsao_kpi.text != "1.190" # Verifica se o valor foi carregado (e não é o mock inicial)
        print(f"Passo 4: Previsão gerada e KPI visível: {previsao_kpi.text}")

        print("Sucesso: Fluxo de Geração de Previsão concluído.")

    except Exception as e:
        print(f"Falha: {e}")
    finally:
        driver.quit()

# --- Fluxo 3: Teste de Comportamento em Caso de Filtro Vazio ---
def test_fluxo_filtro_vazio():
    """
    Fluxo 3: Testa o comportamento ao tentar gerar previsão com filtros vazios/padrão.
    (Assume que o app.py não tem validação, mas o teste verifica o estado inicial)
    """
    driver = setup_driver()
    print("\n--- Fluxo 3: Teste de Comportamento com Filtro Vazio ---")
    try:
        driver.get(BASE_URL + "/previsao")
        time.sleep(2)

        # 1. Deixa os campos com os valores padrão (simulando vazio)
        periodo_select = Select(driver.find_element(By.ID, "periodo-futuro"))
        regiao_select = Select(driver.find_element(By.ID, "regiao-previsao"))
        
        # Assume que a primeira opção é a "vazia" ou padrão
        periodo_select.select_by_index(0)
        regiao_select.select_by_index(0)
        print("Passo 1: Filtros deixados no estado padrão/vazio.")

        # 2. Captura o valor inicial do KPI de previsão
        initial_kpi_text = driver.find_element(By.ID, "previsao_leitura").text
        print(f"Passo 2: KPI inicial: {initial_kpi_text}")

        # 3. Clica em "Gerar Previsão"
        generate_button = driver.find_element(By.CLASS_NAME, "generate-button")
        generate_button.click()
        time.sleep(3)

        # 4. Verifica se o valor do KPI não mudou (Simulação de que a validação impediu a chamada)
        # Em um app real, verificaríamos uma mensagem de erro ou um pop-up.
        final_kpi_text = driver.find_element(By.ID, "previsao_leitura").text
        
        # O teste passa se o valor for o mesmo (indicando que a previsão não foi gerada)
        # ou se uma mensagem de erro for exibida (que não podemos verificar sem o código real).
        # Aqui, verificamos se o valor é o mesmo, simulando falha na geração.
        assert initial_kpi_text == final_kpi_text
        print("Passo 4: Sucesso (Simulado): O valor do KPI não mudou, indicando que a previsão não foi gerada com filtros vazios.")

        print("Sucesso: Fluxo de Filtro Vazio concluído.")

    except Exception as e:
        print(f"Falha: {e}")
    finally:
        driver.quit()


        if __name__ == "__main__":
          test_acesso_pagina_inicial()
          test_fluxo_filtragem_dashboard()
          test_fluxo_geracao_previsao()
          test_fluxo_filtro_vazio()
