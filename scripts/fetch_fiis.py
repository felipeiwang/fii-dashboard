#!/usr/bin/env python3
"""
Atualiza data/fiis.json com dados fundamentalistas dos FIIs do IFIX.
Fontes: Status Invest (VP/cota, DY, ultimo dividendo)
Execucao: python scripts/fetch_fiis.py
          ou automaticamente via GitHub Actions todo dia util as 18h BRT
"""

import json
import time
import datetime
import re
import os
import requests
from bs4 import BeautifulSoup

TICKERS = [
    "KNRI11","HGLG11","XPLG11","VISC11","HSML11","GGRC11","BRCO11","BTLG11",
    "RBVA11","HFOF11","BCFF11","KNCR11","KNHY11","MXRF11","HGRU11","RBRF11",
    "RZTR11","VGHF11","PVBI11","HGPO11","RBRP11","JSRE11","BRCR11","RECT11",
    "LVBI11","TRXF11","SARE11","ALZR11","HGBS11","MALL11","IRDM11","VINO11",
    "RBRR11","XPCM11","BPFF11","CPTS11","VRTA11","HGCR11","MGFF11","URPR11",
    "TORD11","HGRE11","XPML11","VILG11","AFHI11","DEVA11","RCRB11","PLRI11",
    "HCRI11","CARE11","OULG11","PATL11","GZIT11","FLMA11","RBRD11","VSLH11",
    "HSRE11","FVPQ11","CDII11","RZAK11"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fiis.json")


def load_existing():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def fetch_status_invest(ticker: str) -> dict:
    """Busca VP, DY, ultimo dividendo no Status Invest."""
    url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {}

        # VP por cota
        for div in soup.find_all("div", class_="info"):
            title = div.find("span", class_="title")
            value = div.find("strong", class_="value")
            if not title or not value:
                continue
            t = title.get_text(strip=True).lower()
            v_raw = value.get_text(strip=True).replace("R$", "").replace(".", "").replace(",", ".").strip()
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

        # Ultimo dividendo
        div_table = soup.find("table", {"id": re.compile(r"dividend", re.I)})
        if div_table:
            rows = div_table.find_all("tr")
            for row in rows[1:2]:  # primeira linha de dados
                cols = row.find_all("td")
                if len(cols) >= 2:
                    raw_val = cols[1].get_text(strip=True).replace("R$", "").replace(".", "").replace(",", ".").strip()
                    raw_date = cols[0].get_text(strip=True)
                    try:
                        result["lastDiv"] = round(float(raw_val), 4)
                        result["divDate"] = raw_date
                    except ValueError:
                        pass

        return result

    except Exception as e:
        print(f"  [WARN] {ticker}: {e}")
        return {}


def fetch_brapi_fundamentals(ticker: str) -> dict:
    """Fallback: busca VP e DY via brapi.dev (sem token = demo, limitado)."""
    url = f"https://brapi.dev/api/quote/{ticker}?modules=summaryProfile,defaultKeyStatistics&token=demo"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        r = data.get("results", [{}])[0]
        result = {}
        # brapi retorna bookValue para VP/cota em alguns casos
        bv = r.get("bookValue")
        if bv:
            result["vp"] = round(float(bv), 2)
        dy = r.get("dividendYield")
        if dy:
            result["dy"] = round(float(dy) * 100, 2)
        return result
    except Exception as e:
        print(f"  [brapi fallback] {ticker}: {e}")
        return {}


def main():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando atualizacao de dados...")

    existing = load_existing()
    updated = {
        "_meta": {
            "updated": datetime.date.today().isoformat(),
            "source": "Status Invest / brapi.dev",
            "note": "Atualizado automaticamente via GitHub Actions todo dia util as 18h BRT"
        }
    }

    for i, ticker in enumerate(TICKERS, 1):
        print(f"  [{i:02d}/{len(TICKERS)}] {ticker}...", end=" ", flush=True)

        prev = existing.get(ticker, {})
        new_data = fetch_status_invest(ticker)

        if not new_data.get("vp"):
            new_data.update(fetch_brapi_fundamentals(ticker))

        # mescla: mantém campos do JSON anterior se não conseguiu buscar
        merged = {**prev}
        if new_data.get("vp"):
            merged["vp"] = new_data["vp"]
            print(f"VP={new_data['vp']}", end=" ")
        if new_data.get("dy"):
            merged["dy"] = new_data["dy"]
            print(f"DY={new_data['dy']}%", end=" ")
        if new_data.get("pvpRef"):
            merged["pvpRef"] = new_data["pvpRef"]
        if new_data.get("lastDiv"):
            merged["lastDiv"] = new_data["lastDiv"]
            merged["divDate"] = new_data.get("divDate", "")
        print()

        # limpa campos desnecessarios do _meta que podem ter vazado
        for k in ("_meta",):
            merged.pop(k, None)

        updated[ticker] = merged
        time.sleep(1.2)  # respeita rate limit

    # salva
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    ok = sum(1 for t in TICKERS if updated.get(t, {}).get("vp"))
    print(f"\nConcluido: {ok}/{len(TICKERS)} tickers com VP/cota atualizado.")
    print(f"Arquivo salvo em: {DATA_PATH}")


if __name__ == "__main__":
    main()
