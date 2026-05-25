from playwright.sync_api import sync_playwright
import pandas as pd
import time
import hashlib


URL = "https://www.seg-social.pt/ptss/sef/lista-devedores/consulta-lista-devedores?dswid=7612"


# =========================================================
# Esperar AJAX
# =========================================================
def esperar_ajax(page):
    try:
        page.wait_for_selector("#frawPageBlocker_blocker", state="hidden", timeout=30000)
    except:
        pass

    try:
        page.wait_for_selector("#frawPageBlocker", state="hidden", timeout=30000)
    except:
        pass

    page.wait_for_load_state("networkidle")
    time.sleep(1.5)


# =========================================================
# Extrair tabela
# =========================================================
def extrair_tabela(page):
    tabela = page.locator("table")

    headers = tabela.locator("thead tr th").all_inner_texts()

    linhas = tabela.locator("tbody tr")

    dados = []

    for i in range(linhas.count()):
        row = linhas.nth(i)
        cols = row.locator("td").all_inner_texts()
        cols = [c.strip() for c in cols]

        if cols:
            dados.append(cols)

    return headers, dados


# =========================================================
# Fingerprint da tabela (detetar duplicação / falha AJAX)
# =========================================================
def fingerprint_tabela(page):
    linhas = page.locator("table tbody tr")
    texto = linhas.all_inner_texts()
    raw = "|".join(texto)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# =========================================================
# Encontrar dropdown tipo entidade
# =========================================================
def obter_dropdown_tipo(page):
    selects = page.locator("select")

    for i in range(selects.count()):
        s = selects.nth(i)
        options = s.locator("option")

        textos = [options.nth(j).inner_text().strip() for j in range(options.count())]

        if "Pessoas coletivas" in textos:
            return s

    return None


# =========================================================
# Encontrar dropdown escalão
# =========================================================
def obter_dropdown_escalao(page):
    selects = page.locator("select")

    for i in range(selects.count()):
        s = selects.nth(i)
        options = s.locator("option")

        textos = [options.nth(j).inner_text().strip() for j in range(options.count())]

        if any("7500" in t or "1000000" in t for t in textos):
            return s

    return None


# =========================================================
# Obter escalões (VERSÃO FIÁVEL)
# =========================================================
def obter_escaloes_fiavel(page):
    esperar_ajax(page)

    dropdown = obter_dropdown_escalao(page)

    if dropdown is None:
        raise Exception("Dropdown de escalões não encontrado.")

    options = dropdown.locator("option")

    escaloes = []

    for i in range(options.count()):
        texto = options.nth(i).inner_text().strip()

        if texto and "selecion" not in texto.lower():
            escaloes.append(texto)

    # remove duplicados mantendo ordem
    escaloes = list(dict.fromkeys(escaloes))

    print(f"[INFO] Escalões detetados: {len(escaloes)}")
    return escaloes


# =========================================================
# Selecionar tipo coletiva
# =========================================================
def selecionar_coletiva(page):
    print("A selecionar Pessoas coletivas...")

    dropdown = obter_dropdown_tipo(page)

    if dropdown is None:
        raise Exception("Dropdown tipo entidade não encontrado.")

    dropdown.select_option(label="Pessoas coletivas")
    esperar_ajax(page)

    print("OK")


# =========================================================
# Pesquisar
# =========================================================
def clicar_pesquisar(page):
    for _ in range(5):
        try:
            esperar_ajax(page)
            page.get_by_text("Pesquisar").click(force=True)
            break
        except:
            time.sleep(2)

    esperar_ajax(page)


# =========================================================
# Alterar resultados por página
# =========================================================
def alterar_resultados_por_pagina(page):
    selects = page.locator("select")

    for i in range(selects.count()):
        s = selects.nth(i)
        options = s.locator("option")

        textos = [options.nth(j).inner_text().strip() for j in range(options.count())]

        if "10" in textos and "25" in textos and "50" in textos:
            try:
                s.select_option("50")
                esperar_ajax(page)
                print("50 resultados ativado")
                return
            except:
                pass


# =========================================================
# Avançar página
# =========================================================
def avancar_pagina(page):
    next_button = page.locator(
        "a[aria-label='Next Page'], a.ui-paginator-next, .ui-paginator-next"
    )

    if next_button.count() == 0:
        return False

    if "disabled" in (next_button.first.get_attribute("class") or ""):
        return False

    for _ in range(5):
        try:
            esperar_ajax(page)
            next_button.first.click(force=True)
            break
        except:
            time.sleep(2)

    esperar_ajax(page)
    return True


# =========================================================
# Selecionar escalão
# =========================================================
def selecionar_escalao(page, escalao):
    dropdown = obter_dropdown_escalao(page)

    if dropdown is None:
        raise Exception("Dropdown escalão não encontrado.")

    print(f"A selecionar: {escalao}")

    dropdown.select_option(label=escalao)
    esperar_ajax(page)


# =========================================================
# MAIN
# =========================================================
with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("A abrir site...")
    page.goto(URL, timeout=120000)
    esperar_ajax(page)

    selecionar_coletiva(page)

    clicar_pesquisar(page)

    escaloes = obter_escaloes_fiavel(page)

    print("\nEscalões encontrados:")
    print(escaloes)

    todos_dados = []
    resultados_por_escalao = {}

    for escalao in escaloes:

        print("\n" + "=" * 60)
        print(f"ESCALÃO: {escalao}")
        print("=" * 60)

        selecionar_escalao(page, escalao)
        clicar_pesquisar(page)
        alterar_resultados_por_pagina(page)

        pagina = 1
        hashes = set()
        dados_escalao = []

        while True:

            headers, dados = extrair_tabela(page)
            fp = fingerprint_tabela(page)

            # detetar loop ou falha AJAX
            if fp in hashes:
                print("⚠ Página repetida detetada (AJAX instável).")
                break

            hashes.add(fp)

            for row in dados:
                row.append("Pessoa Coletiva")
                row.append(escalao)

            dados_escalao.extend(dados)
            todos_dados.extend(dados)

            print(f"[{escalao}] Página {pagina} -> {len(dados)} linhas")

            if not avancar_pagina(page):
                break

            pagina += 1

        resultados_por_escalao[escalao] = len(dados_escalao)
        print(f"[OK] {escalao}: {len(dados_escalao)} registos")

    # =====================================================
    # VALIDAÇÃO FINAL
    # =====================================================
    print("\n==============================")
    print("VALIDAÇÃO FINAL")
    print("==============================")

    for esc, n in resultados_por_escalao.items():
        print(f"{esc}: {n}")

    faltam = [e for e, n in resultados_por_escalao.items() if n == 0]

    if faltam:
        print("\n⚠ Escalões sem dados:")
        print(faltam)
    else:
        print("\n✅ Todos os escalões foram processados com sucesso.")

    # =====================================================
    # DATAFRAME FINAL
    # =====================================================
    headers.append("Tipo Entidade")
    headers.append("Escalão Dívida")

    df = pd.DataFrame(todos_dados, columns=headers)

    print(df.head())
    print(f"\nTotal registos: {len(df)}")

    # =====================================================
    # EXPORT
    # =====================================================
    df.to_csv("devedores_coletivos.csv", index=False, encoding="utf-8-sig")
    df.to_excel("devedores_coletivos.xlsx", index=False)

    print("\nFicheiros exportados com sucesso.")

    browser.close()