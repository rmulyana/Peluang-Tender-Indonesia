import time
from datetime import datetime, timedelta, date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ================== KONFIGURASI ==================

BASE_URL = "https://www.tender-indonesia.com"
MOBILE_BASE = f"{BASE_URL}/m"

# URL login member (SESUIKAN jika berbeda dengan yang kamu pakai)
LOGIN_URL = f"{BASE_URL}/Project_room/index.php"

# Kredensial akun kamu
USERNAME = "KPMOG"
PASSWORD = "kpm2025"

# Nama field form login (CEK via Inspect Element di browser kamu)
# Biasanya bukan 'username'/'password' polos. Sesuaikan dengan atribut name= di form.
LOGIN_PAYLOAD = {
    "USER ID": USERNAME,   # ganti jadi key yg benar, misal "userid" atau "txtID"
    "PASSWORD": PASSWORD,  # ganti jadi key yg benar, misal "password" atau "txtPWD"
}

# Range tanggal rilis pengumuman yang mau di-scrape (format: YYYY-MM-DD)
START_DATE_STR = "2025-11-01"
END_DATE_STR   = "2025-11-11"

# Output file
OUTPUT_XLSX = "tender_indonesia_filtered.xlsx"

# Delay antar request (detik)
REQUEST_DELAY = 1.0

# =================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TenderScraper/1.0; +https://example.com)"
}


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


START_DATE = parse_date(START_DATE_STR)
END_DATE = parse_date(END_DATE_STR)


def create_session():
    """
    Buat session & login ke Tender-Indonesia pakai akun kamu.
    Kamu WAJIB sudah sesuaikan LOGIN_URL & LOGIN_PAYLOAD dengan form asli.
    """
    s = requests.Session()
    s.headers.update(HEADERS)

    # 1) GET dulu halaman login (buat ambil cookie / token kalau ada)
    r = s.get(LOGIN_URL, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Gagal akses halaman login: {r.status_code}")

    # Kalau ada hidden input (token, dll), tambahkan ke LOGIN_PAYLOAD di sini (optional, tergantung implementasi web)
    soup = BeautifulSoup(r.text, "html.parser")
    for hidden in soup.find_all("input", {"type": "hidden"}):
        name = hidden.get("name")
        value = hidden.get("value", "")
        if name and name not in LOGIN_PAYLOAD:
            LOGIN_PAYLOAD[name] = value

    # 2) POST login
    r2 = s.post(LOGIN_URL, data=LOGIN_PAYLOAD, timeout=15)
    if r2.status_code != 200:
        raise Exception(f"Gagal login: status {r2.status_code}")

    # Validasi kasar: cek ada teks yang mengindikasikan sudah login (sesuaikan dengan tampilan actual)
    if "Logout" not in r2.text and "My Admin" not in r2.text and "Member" not in r2.text:
        # Ini hanya indikasi; kalau salah, cek manual HTML respon dan sesuaikan.
        print("[WARNING] Indikasi login belum jelas. Cek kembali LOGIN_PAYLOAD & LOGIN_URL.")
    else:
        print("[INFO] Login sukses terdeteksi.")

    return s


def generate_date_urls(start_date: date, end_date: date):
    """
    Bangun URL list tender per hari berdasarkan pola:
    - Hari ini biasanya: /m/tender.php
    - Hari lain:         /m/tender-YYYY-MM-DD
    """
    urls = []
    today = datetime.today().date()

    current = start_date
    while current <= end_date:
        if current == today:
            urls.append(f"{MOBILE_BASE}/tender.php")
        else:
            slug = f"tender-{current:%Y-%m-%d}"
            urls.append(f"{MOBILE_BASE}/{slug}")
        current += timedelta(days=1)

    return urls


def get_soup(session: requests.Session, url: str):
    r = session.get(url, timeout=15)
    if r.status_code != 200:
        print(f"[WARN] {url} -> {r.status_code}")
        return None
    return BeautifulSoup(r.text, "html.parser")


def parse_list_page(session: requests.Session, url: str, start_date: date, end_date: date):
    """
    Ambil daftar tender dari halaman list harian.
    Asumsi: setiap baris berbentuk 'dd-mm-YYYY - Judul Tender'
    Filter: hanya ambil yang tanggalnya di antara start_date & end_date (inklusif).
    """
    soup = get_soup(session, url)
    if not soup:
        return []

    results = []

    for a in soup.find_all("a"):
        text = " ".join(a.get_text(strip=True).split())
        if " - " not in text:
            continue

        tanggal_part, title = text.split(" - ", 1)

        # cek pola tanggal
        try:
            tender_date = datetime.strptime(tanggal_part, "%d-%m-%Y").date()
        except ValueError:
            continue

        # filter by date range
        if tender_date < start_date or tender_date > end_date:
            continue

        href = a.get("href") or ""
        if not href:
            continue

        full_url = urljoin(MOBILE_BASE + "/", href)

        results.append({
            "announce_date": tender_date,
            "title": title.strip(),
            "list_text": text,
            "detail_url": full_url
        })

    return results


def parse_detail_page(session: requests.Session, url: str) -> dict:
    """
    Ambil info detail singkat dari halaman detail tender.
    Field disesuaikan dengan layout aktual. Di sini kita pakai pendekatan generic:
    baca teks & tarik nilai setelah label 'xxx :'.
    """
    soup = get_soup(session, url)
    if not soup:
        return {}

    text = soup.get_text("\n", strip=True)

    fields = [
        ("Project Description", "project_description"),
        ("Category", "category"),
        ("Project Owner", "project_owner"),
        ("Qualification", "qualification"),
        ("Estimation Value", "estimation_value"),
        ("Location", "location"),
        ("Closing Date", "closing_date"),
    ]

    data = {}
    for label, key in fields:
        marker = label + " :"
        idx = text.find(marker)
        if idx == -1:
            continue
        after = text[idx + len(marker):].split("\n", 1)[0].strip()
        data[key] = after

    return data


def scrape():
    session = create_session()
    list_urls = generate_date_urls(START_DATE, END_DATE)
    all_rows = []

    print(f"[INFO] Scraping {len(list_urls)} halaman list, range {START_DATE} s/d {END_DATE}")

    for url in list_urls:
        print(f"[LIST] {url}")
        tenders = parse_list_page(session, url, START_DATE, END_DATE)
        print(f"  -> {len(tenders)} tender dalam range")

        for t in tenders:
            detail = parse_detail_page(session, t["detail_url"])
            row = {
                "announce_date": t["announce_date"].isoformat(),
                "title": t["title"],
                "detail_url": t["detail_url"],
                "project_description": detail.get("project_description", ""),
                "category": detail.get("category", ""),
                "project_owner": detail.get("project_owner", ""),
                "qualification": detail.get("qualification", ""),
                "estimation_value": detail.get("estimation_value", ""),
                "location": detail.get("location", ""),
                "closing_date": detail.get("closing_date", ""),
            }
            all_rows.append(row)
            time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    if not all_rows:
        print("[INFO] Tidak ada data dalam range tanggal ini. Cek kembali START_DATE/END_DATE.")
        return

    # Simpan ke Excel
    df = pd.DataFrame(all_rows)
    # Sort by announce_date desc biar enak dibaca
    df = df.sort_values(by="announce_date", ascending=False)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tender")

    print(f"[DONE] {len(all_rows)} baris tersimpan ke {OUTPUT_XLSX}")


if __name__ == "__main__":
    scrape()