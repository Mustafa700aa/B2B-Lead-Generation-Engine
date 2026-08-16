# 🚀 B2B Lead Engine

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-Async-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Pandas](https://img.shields.io/badge/Pandas-Data%20Export-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, OOP-based **B2B Lead Generation Engine** built with **Python**, **Playwright**, **HTTPX**, and **Pandas**. It scrapes business intelligence from Google Maps, enriches leads with contact emails by asynchronously crawling company websites, cleans and standardizes data, and exports formatted Excel reports (`.xlsx`).

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **Google Maps Scraping** | Two-phase architecture: feed collection + detail extraction via Playwright |
| 🛡️ **Crash Resilience** | Immediate SQLite checkpointing with **WAL mode** — no data loss on crashes |
| 🕵️ **Anti-Ban & Stealth** | Rotating user agents, anti-automation flags, configurable proxy support |
| 🚫 **Sponsored Ad Filtering** | Automatically skips paid "Sponsored" / "Ad" listings via URL + badge detection |
| 📧 **Deep Email Enrichment** | Async website crawling (`/contact`, `/about`) with RFC 5322 regex + `mailto:` parsing |
| 📊 **Polished Excel Reports** | Dark-themed headers, zebra striping, clickable hyperlinks, auto-column widths |
| 📝 **Centralized Logging** | Dual output to console (colorized) + rotating `.log` file |

---

## 🏗️ Project Architecture

```
b2b-lead-engine/
├── config.py             # Settings, timeouts, anti-ban headers, selectors, paths
├── models.py             # Lead data model (Pydantic) & serialization
├── logger.py             # Dual console (colorized) & rotating file logging
├── database.py           # SQLite manager with WAL mode & checkpointing
├── scraper.py            # GoogleMapsScraper — Playwright, scroll & ad filtering
├── enricher.py           # DataEnricher — Async HTTPX + regex email extraction
├── exporter.py           # DataExporter — Pandas cleaning + OpenPyXL styling
├── main.py               # Unified CLI orchestrator & pipeline entry point
├── requirements.txt      # Dependency specifications
└── data/                 # Runtime storage (DB, logs, Excel exports)
```

---

## 📦 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/<YOUR_USERNAME>/b2b-lead-engine.git
cd b2b-lead-engine
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browser
```bash
playwright install chromium
```

> **Note:** If Chromium download fails, the engine automatically falls back to system-installed Edge or Chrome.

---

## ⚡ Quick Start

### Run the Full Pipeline
```bash
python main.py --query "Real Estate Agencies in Dubai" --limit 10
```

### Custom Search with More Results
```bash
python main.py --query "Software Companies in London" --limit 25
```

### Run in Headless Mode (No Browser Window)
```bash
python main.py --query "Marketing Agencies in New York" --limit 15 --headless
```

### Enrich Existing Database (Skip Scraping)
```bash
python main.py --skip-scrape
```

### Scrape Without Email Enrichment
```bash
python main.py --query "Dentists in Miami" --limit 20 --skip-enrich
```

---

## 📊 Output

| Output | Location |
|--------|----------|
| 📄 Excel Report | `data/exports/b2b_leads_YYYYMMDD_HHMMSS.xlsx` |
| 🗄️ SQLite Database | `data/leads.db` |
| 📝 Execution Log | `data/logs/b2b_lead_engine.log` |

### Sample Pipeline Output
```
=================================================================
                    PIPELINE EXECUTION SUMMARY
=================================================================
 Total Leads in Database : 5
 Leads with Phone Numbers: 5
 Leads with Websites     : 5
 Enriched Leads          : 5
 Verified Contact Emails : 4
=================================================================
```

---

## 🛠️ Configuration

All settings are centralized in [`config.py`](config.py):

- **Timeouts** — Navigation, element wait, scroll pause
- **User Agents** — Rotating pool of realistic browser fingerprints
- **Proxy Support** — Configure `PROXY_SERVER` for rotating proxies
- **Selectors** — Google Maps DOM selectors (easily updatable)
- **Sponsored Filters** — URL patterns & text markers to skip ads

---

## 🧰 Tech Stack

- **[Playwright](https://playwright.dev/python/)** — Async browser automation for Google Maps
- **[HTTPX](https://www.python-httpx.org/)** — Async HTTP client for website crawling
- **[Pandas](https://pandas.pydata.org/)** — Data cleaning & transformation
- **[OpenPyXL](https://openpyxl.readthedocs.io/)** — Styled Excel report generation
- **[Pydantic](https://docs.pydantic.dev/)** — Data validation & modeling
- **[SQLite (WAL)](https://www.sqlite.org/wal.html)** — Crash-resilient local persistence

---

## ⚠️ Disclaimer

This tool is built for **educational and research purposes**. Always respect the Terms of Service of any website you scrape. The authors are not responsible for any misuse of this software.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
