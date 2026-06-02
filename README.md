# FIIs — IFIX Dashboard

Dashboard pessoal para acompanhamento diário dos FIIs que compõem o IFIX.  
Deploy estático via **GitHub Pages** · Dados fundamentalistas atualizados automaticamente via **GitHub Actions**.

---

## Funcionalidades

- Cotações em tempo real via [brapi.dev](https://brapi.dev)
- VP/cota, P/VP, DY anualizado, último dividendo
- Sparkline de 30 dias por FII
- Variação vs IFIX (alfa do dia)
- Visão consolidada por segmento (Lajes, Logística, Shopping, CRI, etc.)
- Filtros: maiores altas/quedas, P/VP abaixo de 0,90, DY alto, outperformers vs IFIX
- Dados fundamentalistas atualizados automaticamente todo dia útil às 18h

---

## Deploy — passo a passo

### 1. Criar o repositório no GitHub

```bash
# Clone ou crie um novo repo público
git init fii-dashboard
cd fii-dashboard

# Copie todos os arquivos deste projeto para a pasta
# (index.html, data/fiis.json, scripts/fetch_fiis.py, .github/workflows/update-data.yml)

git add .
git commit -m "feat: dashboard FIIs IFIX inicial"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/fii-dashboard.git
git push -u origin main
```

### 2. Ativar o GitHub Pages

1. Acesse o repositório no GitHub
2. Vá em **Settings → Pages**
3. Em **Source**, selecione: `Deploy from a branch`
4. Branch: `main` · Pasta: `/ (root)`
5. Clique em **Save**

Após ~2 minutos, o dashboard estará disponível em:
```
https://SEU-USUARIO.github.io/fii-dashboard
```

### 3. (Opcional) Token brapi.dev para cotações em tempo real

O token `demo` tem limite de requisições. Para uso sem restrição:

1. Crie conta gratuita em [brapi.dev](https://brapi.dev)
2. Copie seu token
3. No `index.html`, linha:
   ```js
   const BRAPI_TOKEN = 'demo';
   ```
   Substitua `demo` pelo seu token.
4. Faça commit e push.

---

## Como os dados são atualizados

### Automático — GitHub Actions

O workflow `.github/workflows/update-data.yml` roda automaticamente todo dia útil às **18h BRT** (após fechamento do pregão) e:

1. Executa `scripts/fetch_fiis.py`
2. Busca VP/cota, DY e último dividendo no Status Invest para cada ticker
3. Atualiza `data/fiis.json`
4. Faz commit automático no repositório

Você pode acompanhar as execuções na aba **Actions** do GitHub. Também é possível disparar manualmente clicando em **"Run workflow"**.

### Manual — edição direta no GitHub

Para atualizar um dado específico sem esperar o Actions:

1. Acesse `data/fiis.json` no GitHub
2. Clique no ícone de lápis (editar)
3. Modifique os campos desejados:
   ```json
   "KNRI11": {
     "vp": 154.80,
     "dy": 7.40,
     "lastDiv": 1.08,
     "divDate": "2025-06-15"
   }
   ```
4. Clique em **Commit changes**

O GitHub Pages atualiza em ~1 minuto após o commit.

---

## Estrutura do projeto

```
fii-dashboard/
├── index.html                        # Dashboard principal
├── data/
│   └── fiis.json                     # Dados fundamentalistas (VP, DY, dividendos)
├── scripts/
│   └── fetch_fiis.py                 # Script de scraping (roda no Actions)
└── .github/
    └── workflows/
        └── update-data.yml           # Automação GitHub Actions
```

---

## Formato do fiis.json

```json
{
  "_meta": {
    "updated": "2025-06-02",
    "source": "Status Invest / brapi.dev"
  },
  "TICKER11": {
    "vp": 152.40,       // Valor patrimonial por cota (R$)
    "dy": 7.20,         // Dividend Yield anualizado (%)
    "lastDiv": 1.05,    // Último dividendo declarado (R$)
    "divDate": "2025-05-15",  // Data do último dividendo (AAAA-MM-DD)
    "pvpRef": 0.97      // P/VP de referência (calculado pelo script)
  }
}
```

---

## Fontes de dados

| Dado | Fonte | Atualização |
|------|-------|-------------|
| Cotação, variação, volume | brapi.dev (API REST) | Tempo real / 5 min |
| Histórico 30 dias (sparkline) | brapi.dev | Diário |
| VP/cota, DY, último dividendo | Status Invest (scraping) | Diário via Actions |

---

## Executar o script de atualização localmente

```bash
pip install requests beautifulsoup4 lxml
python scripts/fetch_fiis.py
```

---

## Licença

Uso pessoal. Dados de mercado sujeitos aos termos de uso de cada fonte.
