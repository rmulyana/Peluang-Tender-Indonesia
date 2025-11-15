import os
import re
import time
import threading
import subprocess
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# =========================
# Helpers: Normalization
# =========================

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def correct_sector_typos(sector_name: str) -> str:
    """
    Normalize common typos / variations in sector name.
    """
    if not sector_name:
        return ""
    name = sector_name.upper().strip()

    corrections = {
        "ELECTRICTY": "ELECTRICITY",
        "ELECTRIC": "ELECTRICITY",
        "ELECTRICITY": "ELECTRICITY",
        "GOVERMENT": "GOVERNMENT",
        "GOVERNMENT": "GOVERNMENT",
        "MANUFACTUR": "MANUFACTURE",
        "MANUFACTURE": "MANUFACTURE",
        "TELECOMMUNICATON": "TELECOMMUNICATION",
        "TELECOMMUNICATION": "TELECOMMUNICATION",
        "INFRASTRUCTUR": "INFRASTRUCTURE",
        "INFRASTRUCTURE": "INFRASTRUCTURE",
        "INTERNATONAL": "INTERNATIONAL",
        "INTERNATIONAL": "INTERNATIONAL",
        "MINING / CEMENT": "MINING / CEMENT",
        "PLANTATION": "PLANTATION",
        "BANK AND FINANCIAL SERVICE": "BANK AND FINANCIAL SERVICE",
        "HOSPITAL": "HOSPITAL",
        "OTHER PRIVATE SECTOR": "OTHER PRIVATE SECTOR",
        "OIL & GAS": "OIL & GAS",
    }

    if name in corrections:
        return corrections[name]

    # partial match fallback
    for wrong, fixed in corrections.items():
        if wrong in name:
            return fixed

    return name


def detect_sector_from_client(client_name: str) -> str:
    """
    Fallback detection of sector based on client keywords.
    """
    if not client_name:
        return ""

    name = client_name.upper()

    # Oil & Gas
    if any(k in name for k in ["PERTAMINA", "PETROCHINA", "MEDCO", "CHEVRON", "SHELL", "MUBADALA", "BP "]):
        return "OIL & GAS"

    # Power / Electricity
    if any(k in name for k in ["PLN", "ELECTRIC", "POWER", "TENAGA LISTRIK"]):
        return "ELECTRICITY"

    # Government
    if any(k in name for k in ["KEMENTERIAN", "PEMERINTAH", "PEMKAB", "PEMKOT", "PEMPROV", "DINAS", "KABUPATEN", "KOTA"]):
        return "GOVERNMENT"

    # Banking & Finance
    if any(k in name for k in ["BANK ", "BPR ", "FINANCE", "ASURANSI"]):
        return "BANK AND FINANCIAL SERVICE"

    # Hospital
    if any(k in name for k in ["RS ", "RUMAH SAKIT", "HOSPITAL", "CLINIC", "KLINIK"]):
        return "HOSPITAL"

    # Plantation / Agro
    if any(k in name for k in ["PLANTATION", "SAWIT", "PALM", "PERKEBUNAN"]):
        return "PLANTATION"

    return ""


# =========================
# Helpers: Date Parsing
# =========================

MONTH_MAP_ID = {
    "JAN": 1, "JANUARI": 1,
    "FEB": 2, "FEBRUARI": 2,
    "MAR": 3, "MARET": 3,
    "APR": 4, "APRIL": 4,
    "MEI": 5,
    "JUN": 6, "JUNI": 6,
    "JUL": 7, "JULI": 7,
    "AGU": 8, "AGS": 8, "AGUSTUS": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OKT": 10, "OKTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DES": 12, "DESEMBER": 12,
}


def parse_date(text: str) -> Optional[datetime]:
    """
    Deteksi tanggal dari satu baris teks dalam berbagai format umum.
    """
    if not text:
        return None
    t = text.strip()

    # dd/mm/yy atau dd/mm/yyyy
    m = re.search(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})", t)
    if m:
        d, mo, y = m.groups()
        d = int(d)
        mo = int(mo)
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d)
        except ValueError:
            return None

    # dd Mon yyyy (ID)
    m = re.search(r"(\d{1,2})\s+([A-Za-z\.]+)\s*(\d{4})?", t)
    if m:
        d = int(m.group(1))
        mon_raw = m.group(2).replace(".", "").upper()
        y = m.group(3)
        mo = MONTH_MAP_ID.get(mon_raw)
        if mo:
            if y:
                year = int(y)
            else:
                year = datetime.now().year
            try:
                return datetime(year, mo, d)
            except ValueError:
                return None

    return None


def format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d")


# =========================
# Parsing Tender Text
# =========================

SECTOR_HEADERS = [
    "OIL & GAS",
    "ELECTRICTY",
    "ELECTRICITY",
    "INFRASTRUCTURE",
    "MINING / CEMENT",
    "PLANTATION",
    "BANK AND FINANCIAL SERVICE",
    "MANUFACTURE",
    "TELECOMMUNICATION",
    "HOSPITAL",
    "INTERNATIONAL",
    "OTHER PRIVATE SECTOR",
    "GOVERNMENT",
]


def looks_like_sector_header(line: str) -> bool:
    line_up = clean_text(line).upper()
    if not line_up:
        return False
    if len(line_up) > 80:
        return False
    return any(line_up == sh or sh in line_up for sh in SECTOR_HEADERS)


def looks_like_client_header(line: str) -> bool:
    """
    Heuristik: baris client biasanya:
    - panjang sedang
    - ada PT / CV / Kementerian / Pemda / dll
    - muncul setelah header sector.
    """
    line_up = clean_text(line).upper()
    if not line_up:
        return False
    if len(line_up) > 120:
        return False

    if any(k in line_up for k in [
        "PT ", "PT.", "CV ", "CV.",
        "KEMENTERIAN", "PEMERINTAH", "PEMKAB", "PEMKOT",
        "DINAS", "UNIVERSITAS", "POLITEKNIK",
        "RUMAH SAKIT", "RS ", "RSU ", "RSUD "
    ]):
        return True

    return False


def extract_tender_items_from_lines(lines: List[str]) -> List[Dict]:
    tenders: List[Dict] = []

    current_sector = ""
    current_client = ""
    buffer_lines: List[str] = []

    def flush_buffer():
        nonlocal buffer_lines
        if not buffer_lines:
            return

        full = clean_text(" ".join(buffer_lines))
        buffer_lines = []
        if not full:
            return

        # tanggal
        dt = parse_date(full)
        tanggal = format_date(dt)

        # default: (SOW) Judul Tender
        sow = ""
        title = full

        # pola: (EPC) Judul...
        m = re.match(r"^\(([^)]+)\)\s*(.+)", full)
        if m:
            sow = clean_text(m.group(1))
            title = clean_text(m.group(2))
        else:
            # pola: SOW: ...   Judul...
            m2 = re.match(r"^SOW\s*[:\-]\s*(.+?)\s{2,}(.+)$", full, flags=re.IGNORECASE)
            if m2:
                sow = clean_text(m2.group(1))
                title = clean_text(m2.group(2))

        # fallback: asumsi 4 kata pertama ~ SOW
        if not sow:
            tokens = title.split()
            if len(tokens) > 4:
                sow = " ".join(tokens[:4])
                title = " ".join(tokens[4:])

        sow = clean_text(sow)
        title = clean_text(title)

        if not title:
            return

        sector_final = correct_sector_typos(current_sector) if current_sector else ""
        if not sector_final and current_client:
            sector_final = detect_sector_from_client(current_client)

        tenders.append({
            "Sector": sector_final,
            "Client": clean_text(current_client),
            "Tanggal Rilis": tanggal,
            "SOW": sow,
            "Judul Tender": title,
        })

    for raw in lines:
        line = clean_text(raw)
        if not line:
            continue

        # header sector
        if looks_like_sector_header(line):
            flush_buffer()
            current_sector = correct_sector_typos(line)
            current_client = ""
            continue

        # client
        if looks_like_client_header(line):
            flush_buffer()
            current_client = line
            continue

        # bullet / nomor -> item baru
        if re.match(r"^[•\-\u2022\u2023\u25E6\d]+[)\.\-\s]", raw.strip()):
            flush_buffer()
            buffer_lines = [line]
            flush_buffer()
            continue

        # akumulasi
        buffer_lines.append(line)

    flush_buffer()
    return tenders


# =========================
# HTML Extraction
# =========================

def extract_text_lines_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")

    texts: List[str] = []

    # ambil teks dari elemen-elemen umum
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "b", "strong", "p", "td", "li", "span"]):
        t = clean_text(tag.get_text(separator=" "))
        if t:
            texts.append(t)

    if not texts:
        all_text = clean_text(soup.get_text(separator="\n"))
        texts = [ln for ln in all_text.split("\n") if clean_text(ln)]

    return texts


# =========================
# Selenium Session Manager
# =========================

class SessionManager:
    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._lock = threading.Lock()

    def _create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")

        driver_path = os.getenv("CHROMEDRIVER_PATH")
        if not driver_path:
            try:
                result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
                path = result.stdout.strip()
                if path:
                    driver_path = path
            except Exception:
                driver_path = None

        if driver_path:
            driver = webdriver.Chrome(driver_path, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)

        return driver

    def get_driver(self) -> webdriver.Chrome:
        with self._lock:
            if self._driver is None:
                self._driver = self._create_driver()
            return self._driver

    def cleanup(self):
        with self._lock:
            if self._driver is not None:
                try:
                    self._driver.quit()
                except Exception:
                    pass
                self._driver = None


# =========================
# Web Scraping Logic
# =========================

def scrape_page_with_selenium(session: SessionManager, url: str, wait_selector: Optional[str] = None) -> str:
    driver = session.get_driver()
    driver.get(url)

    if wait_selector:
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except Exception:
            pass

    time.sleep(2)
    return driver.page_source


# =========================
# I/O helpers
# =========================

def find_candidate_files() -> List[str]:
    exts = (".html", ".htm", ".txt")
    files = [f for f in os.listdir(".") if f.lower().endswith(exts)]
    return sorted(files)


def choose_file_interactively() -> Optional[str]:
    files = find_candidate_files()
    if not files:
        print("Tidak ada file .html/.htm/.txt di folder ini.")
        return None

    print("\nPilih file sumber:")
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")

    while True:
        idx = input("Masukkan nomor file (atau kosong untuk batal): ").strip()
        if not idx:
            return None
        if idx.isdigit() and 1 <= int(idx) <= len(files):
            return files[int(idx) - 1]
        print("Input tidak valid.")


def export_to_excel(tenders: List[Dict], output_name: str = "tender_parsed.xlsx") -> str:
    if not tenders:
        print("Tidak ada data untuk diekspor.")
        return ""

    df = pd.DataFrame(tenders)

    if "Tanggal Rilis" in df.columns:
        df["Tanggal Rilis Sort"] = pd.to_datetime(df["Tanggal Rilis"], errors="coerce")
        df = df.sort_values("Tanggal Rilis Sort", ascending=False).drop(columns=["Tanggal Rilis Sort"])

    df.index = range(1, len(df) + 1)
    df.to_excel(output_name, index_label="No")
    print(f"OK. File disimpan sebagai: {output_name}")
    return output_name


# =========================
# Main Flow
# =========================

def parse_from_local_file() -> List[Dict]:
    filename = choose_file_interactively()
    if not filename:
        return []

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    if filename.lower().endswith((".html", ".htm")):
        lines = extract_text_lines_from_html(content)
    else:
        content = content.replace("\r", "\n")
        lines = [ln for ln in content.split("\n") if clean_text(ln)]

    print(f"Loaded {len(lines)} lines from {filename}")
    tenders = extract_tender_items_from_lines(lines)
    return tenders


def parse_from_web(session: SessionManager) -> List[Dict]:
    url = input("Masukkan URL halaman tender: ").strip()
    if not url:
        return []

    print(f"Load {url} ...")
    html = scrape_page_with_selenium(session, url)

    lines = extract_text_lines_from_html(html)
    print(f"HTML parsed menjadi {len(lines)} baris teks.")
    tenders = extract_tender_items_from_lines(lines)
    return tenders


def main():
    print("=== Tender Parser Hybrid ===")
    print("1. Parse dari file lokal (.html/.txt)")
    print("2. Parse dari halaman web (Selenium)")
    print("3. Keluar")

    session = SessionManager()

    try:
        choice = input("Pilih mode [1/2/3]: ").strip()

        if choice == "1":
            tenders = parse_from_local_file()
        elif choice == "2":
            tenders = parse_from_web(session)
        else:
            return

        if not tenders:
            print("❌ Tidak ada tender yang berhasil diparsing.")
            return

        print(f"✅ Total tender terbaca: {len(tenders)}")

        sample = min(5, len(tenders))
        print("\nSample data:")
        for i in range(sample):
            row = tenders[i]
            print(f"{i+1}. {row.get('Sector','')} | {row.get('Client','')} | {row.get('Tanggal Rilis','')}")
            print(f"   SOW  : {row.get('SOW','')}")
            print(f"   Judul: {row.get('Judul Tender','')[:100]}...")
            print()

        export_to_excel(tenders)

    finally:
        session.cleanup()


if __name__ == "__main__":
    main()