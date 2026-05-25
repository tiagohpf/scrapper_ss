from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
import gc


URL = "https://www.seg-social.pt/ptss/sef/lista-devedores/consulta-lista-devedores?dswid=7612"

OUTPUT_CSV = "pessoas_singulares.csv"


# =========================================================
# Extrair tabela
# =========================================================
def extrair_tabela(page):

    tabela = page.locator("table")

    headers = tabela.locator(
        "thead tr th"
    ).all_inner_texts()

    linhas = tabela.locator("tbody tr")

    dados = []

    for i in range(linhas.count()):

        row = linhas.nth(i)

        cols = row.locator(
            "td"
        ).all_inner_texts()

        cols = [c.strip() for c in cols]

        if cols:
            dados.append(cols)

    return headers, dados


# =========================================================
# Esperar overlays desaparecer
# =========================================================
def esperar_ajax(page):

    try:

        page.wait_for_selector(
            "#frawPageBlocker_blocker",
            state="hidden",
            timeout=60000
        )

    except:
        pass

    try:

        page.wait_for_selector(
            "#frawPageBlocker",
            state="hidden",
            timeout=60000
        )

    except:
        pass


# =========================================================
# Obter dropdowns
# =========================================================
def obter_dropdowns(page):

    selects = page.locator("select")

    dropdown_tipo = None
    dropdown_escalao = None

    for i in range(selects.count()):

        s = selects.nth(i)

        options = s.locator("option")

        textos = []

        for j in range(options.count()):

            textos.append(
                options.nth(j)
                .inner_text()
                .strip()
            )

        # tipo entidade
        if (
            "Pessoas singulares" in textos
            or
            "Pessoas coletivas" in textos
        ):
            dropdown_tipo = s

        # escalão
        elif (
            "7500 a 25000" in textos
            or
            ">= 1000000,01" in textos
        ):
            dropdown_escalao = s

    return dropdown_tipo, dropdown_escalao


# =========================================================
# Selecionar singular
# =========================================================
def selecionar_tipo(page):

    dropdown_tipo, _ = obter_dropdowns(page)

    dropdown_tipo.select_option(
        label="Pessoas singulares"
    )

    page.wait_for_load_state(
        "networkidle"
    )

    time.sleep(2)


# =========================================================
# Obter escalões
# =========================================================
def obter_escaloes(page):

    _, dropdown_escalao = obter_dropdowns(page)

    options = dropdown_escalao.locator(
        "option"
    )

    escaloes = []

    for i in range(options.count()):

        texto = options.nth(i).inner_text().strip()

        if texto:
            escaloes.append(texto)

    return escaloes


# =========================================================
# Selecionar escalão
# =========================================================
def selecionar_escalao(page, escalao):

    _, dropdown_escalao = obter_dropdowns(page)

    dropdown_escalao.select_option(
        label=escalao
    )

    page.wait_for_load_state(
        "networkidle"
    )

    time.sleep(2)


# =========================================================
# Pesquisar
# =========================================================
def pesquisar(page):

    esperar_ajax(page)

    botao = page.get_by_text(
        "Pesquisar"
    )

    for tentativa in range(5):

        try:

            botao.click(
                force=True
            )

            break

        except:

            time.sleep(2)

    page.wait_for_load_state(
        "networkidle"
    )

    time.sleep(3)


# =========================================================
# 50 resultados
# =========================================================
def alterar_resultados(page):

    try:

        dropdown = page.locator(
            "select.ui-paginator-rpp-options"
        )

        if dropdown.count() > 0:

            dropdown.first.select_option(
                "50"
            )

            page.wait_for_load_state(
                "networkidle"
            )

            time.sleep(2)

    except:
        pass


# =========================================================
# Próxima página
# =========================================================
def avancar(page):

    next_button = page.locator(
        "a[aria-label='Next Page'], "
        "a.ui-paginator-next"
    )

    if next_button.count() == 0:
        return False

    classes = next_button.first.get_attribute(
        "class"
    ) or ""

    if "disabled" in classes:
        return False

    esperar_ajax(page)

    for tentativa in range(5):

        try:

            next_button.first.click(
                force=True
            )

            break

        except:

            time.sleep(2)

    page.wait_for_load_state(
        "networkidle"
    )

    time.sleep(2)

    return True


# =========================================================
# MAIN
# =========================================================
with sync_playwright() as p:

    # browser temporário
    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page()

    page.set_default_timeout(
        60000
    )

    page.goto(
        URL,
        timeout=120000
    )

    page.wait_for_load_state(
        "networkidle"
    )

    selecionar_tipo(page)

    escaloes = obter_escaloes(page)

    browser.close()

    print("Escalões encontrados:")
    print(escaloes)

    # =====================================================
    # LOOP ESCALÕES
    # =====================================================
    for escalao in escaloes:

        print()
        print("=" * 60)
        print(f"ESCALÃO: {escalao}")
        print("=" * 60)

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        page.set_default_timeout(
            60000
        )

        page.goto(
            URL,
            timeout=120000
        )

        page.wait_for_load_state(
            "networkidle"
        )

        selecionar_tipo(page)

        selecionar_escalao(
            page,
            escalao
        )

        pesquisar(page)

        alterar_resultados(page)

        headers = None

        pagina = 1

        while True:

            print(
                f"Página {pagina}"
            )

            headers_tmp, dados = extrair_tabela(
                page
            )

            if headers is None:
                headers = headers_tmp

            for row in dados:

                row.append(
                    "Pessoa Singular"
                )

                row.append(
                    escalao
                )

            df = pd.DataFrame(
                dados
            )

            ficheiro_existe = os.path.exists(
                OUTPUT_CSV
            )

            df.to_csv(
                OUTPUT_CSV,
                mode="a",
                header=not ficheiro_existe,
                index=False,
                encoding="utf-8-sig"
            )

            print(
                f"{len(dados)} linhas guardadas."
            )

            sucesso = avancar(page)

            if not sucesso:
                break

            pagina += 1

        browser.close()

        gc.collect()

    print()
    print("SCRAPING CONCLUÍDO.")