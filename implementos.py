from playwright.sync_api import sync_playwright
import re, time, random, pandas as pd

NBSP = "\xa0"

URL_QUEROTRUCK = "https://querotruck.com.br/anuncios/pesquisa-veiculos?categoria=IMPLEMENTOS&sortType=asc&sortField=OrderedAt&pageSize=40&pageIndex=1"

def jitter(a=0.5, b=1.2): time.sleep(random.uniform(a,b))

def inner_text_or_default(locator, timeout=2500, default="Não informado"):
    try:
        t = locator.inner_text(timeout=timeout)
        return (t or "").replace(NBSP, " ").strip() or default
    except Exception:
        return default

def first_non_empty(card, selectors, timeout=2500, attr=None):
    for sel in selectors:
        try:
            loc = card.locator(sel)
            if loc.count() == 0:
                continue
            if attr:
                val = loc.first.get_attribute(attr)
                if val and val.strip():
                    return val.strip()
            else:
                txt = loc.first.inner_text(timeout=timeout)
                if txt and txt.strip():
                    return txt.replace(NBSP, " ").strip()
        except Exception:
            pass
    return "Não informado"

def normalize_price(s):
    if not s or s == "Não informado": return s
    m = re.search(r'R\$\s*([\d\.\,]+)', s)
    return f'R$ {m.group(1)}' if m else s

def normalize_km(s):
    if not s or s == "Não informado": return s
    low = s.lower().replace("quilometragem", "")
    m = re.search(r'([\d\.]+)\s*km', low)
    if m:
        return f"{m.group(1).replace('.','')} km"
    m2 = re.search(r'([\d\.]+)', s)
    return (m2.group(1).replace('.','') + " km") if m2 else s

SEL = {
    # lista de cards (generalizada)
    "card": [
        "css=div.list-content div.cards app-truck-card",
        "css=app-truck-card"
    ],

    # Implemento/Modelo (h2)
    "implemento": [
        "css=div > a > div > div > h2",
        "xpath=.//div/a/div/div/h2"
    ],

    # Preço (h4)
    "preco": [
        "css=div > a > div > div > h4",
        "xpath=.//div/a/div/div/h4",
        "xpath=.//*[contains(normalize-space(.), 'R$')]"
    ],

    # Km
    "km": [
        "css=div > a > div > div > div > div.row-item-adv > div:nth-child(1)",
        "xpath=.//div/a/div/div/div/div[contains(@class,'row-item-adv')]/div[1]"
    ],

    # Ano
    "ano": [
        "css=div > a > div > div > div > div.row-item-adv > div:nth-child(2)",
        "xpath=.//div/a/div/div/div/div[contains(@class,'row-item-adv')]/div[2]"
    ],

    # Anunciante
    "anunciante": [
        "css=div > a > div > div > div > div.item-adv.ng-star-inserted > span",
        "xpath=.//div/a/div/div/div/div[contains(@class,'item-adv')]/span"
    ],

    # Localização
    "local": [
        "css=div > a > div > div > div > div:nth-child(3) > span",
        "xpath=.//div/a/div/div/div/div[3]/span"
    ],

    # Paginação — novos seletores priorizados (seus), mais fallbacks
    "next_btn": [
        # seus seletores (CSS e XPath absolutos do botão "próxima página"):
        "css=body > app-root > div > app-list-advertisements > app-page-list-ads > main > div > div > div > div.list-content > div.wrap-pagination.ng-star-inserted > div > p-paginator > div > button.p-paginator-next.p-paginator-element.p-link.p-ripple",
        "xpath=/html/body/app-root/div/app-list-advertisements/app-page-list-ads/main/div/div/div/div[2]/div[3]/div/p-paginator/div/button[3]",

        # fallbacks genéricos
        "css=button.p-paginator-next.p-paginator-element.p-link.p-ripple",
        "css=button.p-paginator-next",
        "xpath=//button[contains(@class,'p-paginator-next')]",
        "css=li.p-paginator-next button, li.p-paginator-next a"
    ]
}

SCROLL_STEPS = 3
HEADLESS = True

def extrair_card(card):
    implemento = first_non_empty(card, SEL["implemento"])
    preco = normalize_price(first_non_empty(card, SEL["preco"]))
    km = normalize_km(first_non_empty(card, SEL["km"]))
    ano_txt = first_non_empty(card, SEL["ano"])
    m_ano = re.search(r"\b(19|20)\d{2}(?:/(19|20)\d{2})?\b", ano_txt) if ano_txt != "Não informado" else None
    ano = m_ano.group(0) if m_ano else ano_txt

    anunciante = first_non_empty(card, SEL["anunciante"])
    local = first_non_empty(card, SEL["local"])

    # Marca/Modelo a partir do título (implemento)
    marca, modelo = "Não informado", "Não informado"
    if implemento != "Não informado":
        parts = implemento.split(" ", 1)
        marca = parts[0]
        if len(parts) > 1:
            modelo = parts[1]

    # fallback leve
    if modelo == "Não informado" or (preco == "Não informado" and km == "Não informado" and ano == "Não informado"):
        raw = inner_text_or_default(card)
        if implemento == "Não informado" and raw:
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            if lines:
                parts = lines[0].split(" ", 1)
                marca = parts[0]
                if len(parts) > 1:
                    modelo = parts[1]
        if preco == "Não informado":
            preco = normalize_price(raw)
        if km == "Não informado":
            km = normalize_km(raw)
        if ano == "Não informado":
            m = re.search(r"\b(19|20)\d{2}(?:/(19|20)\d{2})?\b", raw or "")
            if m: ano = m.group(0)
        if local == "Não informado" and raw:
            mloc = re.search(r"[A-Za-zÀ-ÿ\s]+[-–]\s?[A-Z]{2}\b", raw)
            if mloc: local = mloc.group(0).strip()

    return {
        "Marca": marca,
        "Modelo": modelo,
        "Preço": preco,
        "Quilometragem": km,
        "Ano": ano,
        "Anunciante": anunciante,
        "Localização": local,
        "Fonte": "QueroTruck"
    }

def coletar_querotruck(url=URL_QUEROTRUCK):
    resultados = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.goto(url, timeout=320000)
        page.wait_for_load_state("domcontentloaded", timeout=320000)

        page_idx = 1
        while True:
            print(f"[QueroTruck] Página {page_idx} — carregando cards…")

            # lazy-load/scroll
            for _ in range(SCROLL_STEPS):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                jitter(0.6, 1.2)

            # achar cards
            cards = None
            for sel in SEL["card"]:
                try:
                    page.wait_for_selector(sel, timeout=15000, state="attached")
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        cards = loc
                        break
                except Exception:
                    continue

            if cards is None:
                print("[QueroTruck] Nenhum card encontrado.")
                break

            total = cards.count()
            print(f"[QueroTruck] {total} cards encontrados")

            for i in range(total):
                card = cards.nth(i)
                try:
                    item = extrair_card(card)
                    resultados.append(item)
                except Exception as e:
                    print(f"[QueroTruck] Erro ao extrair card {i}: {e}")

            # próxima página
            avancou = False
            for sel_next in SEL["next_btn"]:
                try:
                    btn = page.locator(sel_next)
                    if btn.count() == 0:
                        continue
                    el = btn.first
                    if not el.is_visible():
                        continue
                    disabled = el.get_attribute("disabled")
                    klass = (el.get_attribute("class") or "").lower()
                    if (not disabled) and ("p-disabled" not in klass):
                        print(f"[QueroTruck] Próxima página via: {sel_next}")
                        el.scroll_into_view_if_needed(timeout=3000)
                        el.click()
                        page.wait_for_load_state("domcontentloaded", timeout=320000)
                        jitter(0.7, 1.4)
                        page_idx += 1
                        avancou = True
                        break
                except Exception as e:
                    print(f"[QueroTruck] Falha no próximo ('{sel_next}'): {e}")

            if not avancou:
                print("[QueroTruck] Última página ou sem botão de próxima.")
                break

        browser.close()
    return resultados

if __name__ == "__main__":
    dados = coletar_querotruck()
    df = pd.DataFrame(dados)
    df.to_excel("querotruck.xlsx", index=False)
    print("Exportado: querotruck.xlsx")
