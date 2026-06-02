#!/usr/bin/env python3
"""
Atualiza data/fiis.json com dados fundamentalistas dos FIIs do IFIX.
- Lista de tickers buscada dinamicamente do fiis.com.br (sempre atualizada)
- VP/cota, DY, ultimo dividendo: Status Invest
- Fallback: brapi.dev
Execucao: python scripts/fetch_fiis.py
          ou automaticamente via GitHub Actions todo dia util as 18h BRT
"""

import json, time, datetime, re, os
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fiis.json")

# Segmentos por ticker (mantidos localmente — raramente mudam)
SEGMENTS = {
    # CRI / Papel
    "CACR11":"CRI","AFHI11":"CRI","RZAT11":"CRI","AZPL11":"CRI","BCRI11":"CRI",
    "BTCI11":"CRI","CPTS11":"CRI","ICRI11":"CRI","CPSH11":"CRI","CYCR11":"CRI",
    "DEVA11":"CRI","VRTA11":"CRI","HCTR11":"CRI","HGCR11":"CRI","HTMX11":"CRI",
    "HSAF11":"CRI","IRIM11":"CRI","ITRI11":"CRI","JSAF11":"CRI","KCRE11":"CRI",
    "KNHY11":"CRI","KNIP11":"CRI","KNCR11":"CRI","KNSC11":"CRI","KNUQ11":"CRI",
    "KIVO11":"CRI","KORE11":"CRI","MCCI11":"CRI","MCRE11":"CRI","MXRF11":"CRI",
    "OUJP11":"CRI","PCIP11":"CRI","PSEC11":"CRI","RPRI11":"CRI","RBRL11":"CRI",
    "RBRR11":"CRI","RBRX11":"CRI","RBRY11":"CRI","RECR11":"CRI","RBFM11":"CRI",
    "RZAK11":"CRI","RZTR11":"CRI","SNCI11":"CRI","URPR11":"CRI","VGIP11":"CRI",
    "VGIR11":"CRI","VCJR11":"CRI","VGRI11":"CRI","VRTM11":"CRI","XPCI11":"CRI",
    "XPIN11":"CRI","XPSF11":"CRI","BTAL11":"CRI","BTHF11":"CRI","PMLL11":"CRI",
    "TRBL11":"CRI",
    # Logística
    "ALZR11":"LOG","BRCO11":"LOG","BTLG11":"LOG","FATN11":"LOG","BCIA11":"LOG",
    "CLIN11":"LOG","GGRC11":"LOG","HGLG11":"LOG","HSLG11":"LOG","LVBI11":"LOG",
    "MANA11":"LOG","SNEL11":"LOG","TGAR11":"LOG","VILG11":"LOG","XPLG11":"LOG",
    # Lajes Corporativas
    "BBIG11":"LJ","BRCR11":"LJ","BROF11":"LJ","GTWR11":"LJ","HGRE11":"LJ",
    "JSRE11":"LJ","KNRI11":"LJ","PVBI11":"LJ","RBRP11":"LJ","RCRB11":"LJ",
    "TEPP11":"LJ","TOPP11":"LJ","TRXF11":"LJ","TVRI11":"LJ","VINO11":"LJ",
    # Shopping
    "BPML11":"SHO","GARE11":"SHO","GZIT11":"SHO","HGBS11":"SHO","HSML11":"SHO",
    "SPXS11":"SHO","VISC11":"SHO","WHGR11":"SHO","XPML11":"SHO",
    # Residencial
    "HABT11":"RES","HGRU11":"RES","KISU11":"RES","LIFE11":"RES","PORD11":"RES",
    # Híbrido / FOF
    "HFOF11":"HYB","KFOF11":"HYB","KNHF11":"HYB","MFII11":"HYB","RBVA11":"HYB",
    "SNFF11":"HYB","VGHF11":"HYB",
}


def fetch_ifix_tickers() -> list[tuple[str, str]]:
    """Busca lista atualizada de tickers do IFIX em fiis.com.br."""
    print("  Buscando composicao atual do IFIX em fiis.com.br...")
    try:
        resp = requests.get("https://fiis.com.br/ifix/", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tickers = []
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"/[a-z]{4}11/")):
            ticker = a.get_text(strip=True).upper()
            if re.match(r"^[A-Z]{4}11$", ticker) and ticker not in seen:
                seen.add(ticker)
                seg = SEGMENTS.get(ticker, "HYB")
                tickers.append((ticker, seg))
        if len(tickers) >= 50:
            print(f"  {len(tickers)} tickers encontrados no IFIX.")
            return tickers
    except Exception as e:
        print(f"  [WARN] Nao foi possivel buscar lista do IFIX: {e}")

    # Fallback: lista conhecida hardcoded
    print("  Usando lista fallback hardcoded.")
    return [(t, s) for t, s in SEGMENTS.items()]


def load_existing() -> dict:
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def fetch_status_invest(ticker: str) -> dict:
    """Busca VP, DY e ultimo dividendo no Status Invest."""
    url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        result = {}

        for div in soup.find_all("div", class_="info"):
            title = div.find("span", class_="title")
            value = div.find("strong", class_="value")
            if not title or not value:
                continue
            t = title.get_text(strip=True).lower()
            v_raw = (value.get_text(strip=True)
                     .replace("R$", "").replace(".", "").replace(",", ".").strip())
            try:
                v = float(v_raw)
            except ValueError:
                continue
            if "valor patrimonial" in t or "vp/cota" in t:
                result["vp"] = round(v, 2)
            elif "dy" in t or "dividend yield" in t:
                result["dy"] = round(v, 2)
            elif "p/vp" in t:
                result["pvpRef"] = round(v, 2)

        div_table = soup.find("table", {"id": re.compile(r"dividend", re.I)})
        if div_table:
            for row in div_table.find_all("tr")[1:2]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    raw_val = (cols[1].get_text(strip=True)
                               .replace("R$", "").replace(".", "").replace(",", ".").strip())
                    raw_date = cols[0].get_text(strip=True)
                    try:
                        result["lastDiv"] = round(float(raw_val), 4)
                        result["divDate"] = raw_date
                    except ValueError:
                        pass
        return result
    except Exception as e:
        print(f"[WARN] {ticker}: {e}")
        return {}


def fetch_brapi_fundamentals(ticker: str) -> dict:
    """Fallback via brapi.dev."""
    url = f"https://brapi.dev/api/quote/{ticker}?modules=summaryProfile,defaultKeyStatistics&token=demo"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        r = resp.json().get("results", [{}])[0]
        result = {}
        if bv := r.get("bookValue"):
            result["vp"] = round(float(bv), 2)
        if dy := r.get("dividendYield"):
            result["dy"] = round(float(dy) * 100, 2)
        return result
    except Exception as e:
        print(f"[brapi fallback] {ticker}: {e}")
        return {}


def main():
    now = datetime.datetime.now()
    ref_month = now.strftime("%m/%Y")  # ex: "06/2025"
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando atualizacao — referencia: {ref_month}")

    tickers = fetch_ifix_tickers()
    existing = load_existing()

    updated = {
        "_meta": {
            "updated": datetime.date.today().isoformat(),
            "refMonth": ref_month,
            "source": "Status Invest / brapi.dev",
            "tickerCount": len(tickers),
            "note": "Atualizado automaticamente via GitHub Actions todo dia util as 18h BRT"
        }
    }

    for i, (ticker, seg) in enumerate(tickers, 1):
        print(f"  [{i:02d}/{len(tickers)}] {ticker}...", end=" ", flush=True)

        prev = existing.get(ticker, {})
        new_data = fetch_status_invest(ticker)
        if not new_data.get("vp"):
            new_data.update(fetch_brapi_fundamentals(ticker))

        merged = {**prev}
        merged["seg"] = seg

        if new_data.get("vp"):
            merged["vp"] = new_data["vp"]
            merged["vpMonth"] = ref_month   # mes/ano da referencia
            print(f"VP={new_data['vp']}", end=" ")
        if new_data.get("dy"):
            merged["dy"] = new_data["dy"]
            merged["dyMonth"] = ref_month   # mes/ano da referencia
            print(f"DY={new_data['dy']}%", end=" ")
        if new_data.get("pvpRef"):
            merged["pvpRef"] = new_data["pvpRef"]
        if new_data.get("lastDiv"):
            merged["lastDiv"] = new_data["lastDiv"]
            merged["divDate"] = new_data.get("divDate", "")
        merged.pop("_meta", None)
        print()

        updated[ticker] = merged
        time.sleep(1.2)

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    ok = sum(1 for t, _ in tickers if updated.get(t, {}).get("vp"))
    print(f"\nConcluido: {ok}/{len(tickers)} tickers com VP/cota atualizado.")
    print(f"Arquivo: {DATA_PATH}")


if __name__ == "__main__":
    main()
