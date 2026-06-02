#!/usr/bin/env python3
"""
Atualiza data/fiis.json com dados fundamentalistas dos FIIs do IFIX.

Fontes:
  - Lista IFIX: fiis.com.br (dinâmica) ou fallback hardcoded B3
  - P/VP, caixa%, último rendimento: Status Invest API interna
  - Fallback de P/VP: calculado via VP/cota do Investidor10

Execução: python scripts/fetch_fiis.py
          ou automaticamente via GitHub Actions todo dia útil às 18h BRT
"""

import json, time, datetime, re, os, sys
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "application/json, text/html, */*",
}

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fiis.json")

# ── Segmentos oficiais B3 ───────────────────────────────────────────────
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


def load_existing() -> dict:
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def fetch_ifix_tickers() -> list:
    """Busca composição atual do IFIX em fiis.com.br."""
    print("  Buscando composição IFIX em fiis.com.br...")
    try:
        r = requests.get("https://fiis.com.br/ifix/", headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        tickers, seen = [], set()
        for a in soup.find_all("a", href=re.compile(r"/[a-z]{4}11/")):
            tk = a.get_text(strip=True).upper()
            if re.match(r"^[A-Z]{4}11$", tk) and tk not in seen:
                seen.add(tk)
                tickers.append((tk, SEGMENTS.get(tk, "HYB")))
        if len(tickers) >= 80:
            print(f"  {len(tickers)} tickers encontrados.")
            return tickers
    except Exception as e:
        print(f"  [WARN] fiis.com.br: {e}")
    print("  Usando lista fallback B3.")
    return [(t, s) for t, s in SEGMENTS.items()]


def fetch_status_invest(ticker: str) -> dict:
    """
    Busca P/VP, caixa% e último rendimento via API interna do Status Invest.
    O site usa endpoint JSON próprio que é mais estável que scraping HTML.
    """
    result = {}

    # ── Endpoint 1: dados gerais / indicadores ──────────────────────────
    try:
        url = f"https://statusinvest.com.br/fii/tickerprice?ticker={ticker}&type=4"
        hdrs = {**HEADERS, "Referer": f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}",
                "X-Requested-With": "XMLHttpRequest"}
        r = requests.get(url, headers=hdrs, timeout=15)
        if r.status_code == 200:
            j = r.json()
            # mapear campos — o SI retorna estrutura variada
            for key in ("p_vp", "pvp", "p/vp"):
                if j.get(key) not in (None, "", 0):
                    try: result["pvp_live"] = float(str(j[key]).replace(",",".")); break
                    except: pass
            for key in ("ativo_caixa_porcent", "caixa_porcent", "caixa", "cash_porcent"):
                if j.get(key) not in (None, ""):
                    try: result["caixa"] = float(str(j[key]).replace(",",".")); break
                    except: pass
    except Exception as e:
        print(f"    [SI API1] {ticker}: {e}")

    # ── Endpoint 2: último rendimento ────────────────────────────────────
    try:
        url2 = f"https://statusinvest.com.br/fii/dividends?ticker={ticker}"
        hdrs2 = {**HEADERS, "Referer": f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}",
                 "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
        r2 = requests.get(url2, headers=hdrs2, timeout=15)
        if r2.status_code == 200:
            j2 = r2.json()
            # estrutura esperada: lista de dividendos ordenada por data desc
            divs = j2 if isinstance(j2, list) else j2.get("assetEarningsModels", [])
            if divs:
                last = divs[0]
                for key in ("earningsPerShare", "value", "provento", "rendimento"):
                    if last.get(key) not in (None, ""):
                        try: result["lastRend"] = float(str(last[key]).replace(",",".")); break
                        except: pass
                for key in ("paymentDate", "ed", "dataCom", "data"):
                    if last.get(key):
                        result["lastRendDate"] = str(last[key])[:10]; break
    except Exception as e:
        print(f"    [SI API2] {ticker}: {e}")

    # ── Fallback: scraping da página HTML ────────────────────────────────
    if not result.get("pvp_live") or not result.get("lastRend"):
        try:
            url3 = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
            hdrs3 = {**HEADERS, "Referer": "https://statusinvest.com.br/fundos-imobiliarios"}
            r3 = requests.get(url3, headers=hdrs3, timeout=20)
            if r3.status_code == 200:
                soup = BeautifulSoup(r3.text, "lxml")

                for div in soup.find_all("div", class_="info"):
                    title = div.find(["span","h3"], class_="title")
                    value = div.find(["strong","span"], class_="value")
                    if not title or not value: continue
                    t = title.get_text(strip=True).lower()
                    v_raw = value.get_text(strip=True).replace("R$","").replace(".","").replace(",",".").strip()
                    try:
                        v = float(v_raw)
                        if ("p/vp" in t or "pvp" in t) and not result.get("pvp_live"):
                            result["pvp_live"] = v
                        elif ("caixa" in t or "liquidez" in t) and "%" in value.get_text() and not result.get("caixa"):
                            result["caixa"] = v
                    except: pass

                # Último rendimento — busca no histórico de dividendos da página
                for table in soup.find_all("table"):
                    rows_t = table.find_all("tr")
                    if len(rows_t) >= 2:
                        header = [th.get_text(strip=True).lower() for th in rows_t[0].find_all(["th","td"])]
                        if any("rendimento" in h or "valor" in h or "provento" in h for h in header):
                            cols = rows_t[1].find_all("td")
                            if len(cols) >= 2:
                                for ci, col in enumerate(cols):
                                    v_raw = col.get_text(strip=True).replace("R$","").replace(".","").replace(",",".").strip()
                                    try:
                                        v = float(v_raw)
                                        if 0.01 < v < 50 and not result.get("lastRend"):
                                            result["lastRend"] = v
                                    except: pass
                                # data
                                date_pattern = re.compile(r"\d{2}/\d{2}/\d{4}")
                                for col in cols:
                                    m = date_pattern.search(col.get_text())
                                    if m and not result.get("lastRendDate"):
                                        result["lastRendDate"] = m.group(); break
                            break
        except Exception as e:
            print(f"    [SI scrape] {ticker}: {e}")

    return result


def main():
    now = datetime.datetime.now()
    ref_month = now.strftime("%m/%Y")
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando atualização — ref: {ref_month}")

    tickers  = fetch_ifix_tickers()
    existing = load_existing()

    updated = {
        "_meta": {
            "updated":    datetime.date.today().isoformat(),
            "refMonth":   ref_month,
            "source":     "Status Invest",
            "tickerCount": len(tickers),
            "note":       "Atualizado via GitHub Actions todo dia útil 18h BRT"
        }
    }

    ok_pvp, ok_rend, ok_caixa = 0, 0, 0

    for i, (ticker, seg) in enumerate(tickers, 1):
        print(f"  [{i:03d}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        prev   = existing.get(ticker, {})
        new_d  = fetch_status_invest(ticker)

        merged = {**prev, "seg": seg}

        if new_d.get("pvp_live"):
            merged["pvp_live"] = new_d["pvp_live"]
            ok_pvp += 1
            print(f"PVP={new_d['pvp_live']:.2f}", end=" ")
        if new_d.get("caixa") is not None:
            merged["caixa"] = new_d["caixa"]
            ok_caixa += 1
            print(f"CX={new_d['caixa']:.1f}%", end=" ")
        if new_d.get("lastRend"):
            merged["lastRend"]     = new_d["lastRend"]
            merged["lastRendDate"] = new_d.get("lastRendDate", "")
            ok_rend += 1
            print(f"REND={new_d['lastRend']:.4f}", end=" ")

        merged.pop("_meta", None)
        updated[ticker] = merged
        print()
        time.sleep(1.5)  # respeita rate limit do SI

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"Concluído: {len(tickers)} tickers")
    print(f"  P/VP:           {ok_pvp}/{len(tickers)}")
    print(f"  Caixa%:         {ok_caixa}/{len(tickers)}")
    print(f"  Último rendim.: {ok_rend}/{len(tickers)}")
    print(f"  Arquivo: {DATA_PATH}")


if __name__ == "__main__":
    main()
