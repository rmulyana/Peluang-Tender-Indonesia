import pandas as pd
import re
from datetime import datetime
import time
import os
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pyperclip
import subprocess

def correct_sector_typos(sector_name):
    """
    Correct common typos in sector names
    """
    corrections = {
        'ELECTRICTY': 'ELECTRICITY',
        'GOVERMENT': 'GOVERNMENT',
        'MANUFACTUR': 'MANUFACTURE',
        'TELECOMMUNICATON': 'TELECOMMUNICATION',
        'INFRASTRUCTUR': 'INFRASTRUCTURE',
        'INTERNATONAL': 'INTERNATIONAL',
        'CENTRAL GOVERMENT': 'GOVERNMENT',
        'PROVINCE GOVERMENT': 'GOVERNMENT', 
        'CITY GOVERMENT': 'GOVERNMENT',
        'REGENCY GOVERMENT': 'GOVERNMENT',
        'ALL GOVERMENT': 'GOVERNMENT'
    }
    
    if sector_name in corrections:
        return corrections[sector_name]
    
    return sector_name

def detect_sector_from_client(client_name):
    """
    Detect sector based on client name
    """
    if not client_name or client_name == "Unknown Client":
        return "OTHER PRIVATE SECTOR"
        
    client_upper = client_name.upper()
    
    # Oil & Gas
    if any(keyword in client_upper for keyword in ['PERTAMINA', 'PETROCHINA', 'SHELL', 'EXXON', 'CHEVRON']):
        return "OIL & GAS"
    
    # Government
    if any(keyword in client_upper for keyword in ['KEMENTERIAN', 'BADAN', 'PROVINSI', 'KOTA', 'KABUPATEN', 'BUPATI', 'WALIKOTA', 'GUBERNUR']):
        return "GOVERNMENT"
    
    # Electricity/Energy
    if any(keyword in client_upper for keyword in ['PLN', 'ELECTRIC', 'ENERGI', 'POWER', 'LISTRIK', 'DONGFANG']):
        return "ELECTRICITY"
    
    # Mining
    if any(keyword in client_upper for keyword in ['MINING', 'TAMBANG', 'COAL', 'BATUBARA']):
        return "MINING / CEMENT"
    
    # Bank/Financial
    if any(keyword in client_upper for keyword in ['BANK', 'FINANCE', 'ASURANSI']):
        return "BANK AND FINANCIAL SERVICE"
    
    return "OTHER PRIVATE SECTOR"

def parse_tender_data_smart(text_content):
    """
    Smart parsing function untuk text yang di-copy paste
    """
    print("🔄 SMART PARSING STARTED...")
    
    lines = text_content.split('\n')
    tenders = []
    
    current_sector = ""
    current_client = ""
    
    print(f"📊 Total lines to process: {len(lines)}")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line or len(line) < 2:
            i += 1
            continue
        
        # 1. Detect sector headers
        sector_headers = [
            'OIL & GAS', 'ELECTRICTY', 'ELECTRICITY', 'INFRASTRUCTURE',
            'MINING / CEMENT', 'PLANTATION', 'BANK AND FINANCIAL SERVICE',
            'MANUFACTURE', 'TELECOMMUNICATION', 'HOSPITAL', 'INTERNATIONAL',
            'OTHER PRIVATE SECTOR', 'GOVERNMENT', 'CENTRAL GOVERMENT',
            'PROVINCE GOVERMENT', 'CITY GOVERMENT', 'REGENCY GOVERMENT', 'ALL GOVERMENT'
        ]
        
        for sector in sector_headers:
            if sector in line.upper() and len(line) < 100:
                corrected_sector = correct_sector_typos(sector.upper())
                if current_sector != corrected_sector:
                    current_sector = corrected_sector
                    current_client = ""
                    print(f"✅ SECTOR: {current_sector}")
                break
        
        # 2. Detect client (simple logic)
        is_potential_client = (
            len(line) > 3 and 
            len(line) < 100 and
            not '(2025-' in line and
            not any(sector in line.upper() for sector in sector_headers) and
            not line.startswith('o') and
            not line.startswith('•') and
            not line.startswith(')') and
            not 'DALAM PROSES ENTRI DATA' in line.upper() and
            any(pattern in line.upper() for pattern in [
                'PT ', 'CV ', 'KEMENTERIAN', 'BADAN', 'PROVINSI', 'KOTA', 
                'KABUPATEN', 'PERTAMINA', 'PETROCHINA', 'DONGFANG'
            ])
        )
        
        if is_potential_client:
            client_name = line.split('(')[0].split('-')[0].strip()
            
            if len(client_name) > 3:
                current_client = client_name
                if not current_sector:
                    current_sector = detect_sector_from_client(current_client)
                print(f"✅ CLIENT: {current_client} -> {current_sector}")
        
        # 3. TENDER PARSING - Simple pattern matching
        if '(2025-' in line:
            # Pattern untuk: o (2025-11-10) (SOW) Judul
            patterns = [
                r'[o•]\s+\((\d{4}-\d{2}-\d{2})\)\s+\(([^)]+)\)\s+(.+)',
                r'\((\d{4}-\d{2}-\d{2})\)\s+\(([^)]+)\)\s+(.+)',
                r'[o•]\s+\((\d{4}-\d{2}-\d{2})\)\s+\(([^)]+)\)\s+\)\s*(.+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    date = match.group(1)
                    sow = match.group(2).strip()
                    title = match.group(3).strip()
                    
                    # Clean title
                    title = re.sub(r'^\)\s*', '', title)
                    
                    # Jika tidak ada client, cari dari line sebelumnya
                    if not current_client and i > 0:
                        for j in range(i-1, max(0, i-3), -1):
                            prev_line = lines[j].strip()
                            if (prev_line and 
                                not '(2025-' in prev_line and
                                len(prev_line) > 3 and len(prev_line) < 100):
                                potential_client = prev_line.split('(')[0].split('-')[0].strip()
                                if len(potential_client) > 3:
                                    current_client = potential_client
                                    if not current_sector:
                                        current_sector = detect_sector_from_client(current_client)
                                    break
                    
                    # Final fallback
                    if not current_client:
                        current_client = "Unknown Client"
                    if not current_sector:
                        current_sector = "OTHER PRIVATE SECTOR"
                    
                    # Validasi dan simpan
                    if (title and len(title) > 5 and 
                        re.match(r'\d{4}-\d{2}-\d{2}', date) and
                        len(sow) > 2):
                        
                        tender_data = {
                            'Sector': current_sector,
                            'Client': current_client,
                            'Tanggal Rilis': date,
                            'SOW': sow,
                            'Judul Tender': title
                        }
                        
                        # Cek duplikat
                        is_duplicate = False
                        for existing in tenders:
                            if (existing['Judul Tender'] == title and 
                                existing['Client'] == current_client):
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            tenders.append(tender_data)
                            print(f"✅ TENDER: {current_client} | {date} | {sow} | {title[:60]}...")
                    
                    break
        
        i += 1
    
    print(f"🎯 TOTAL TENDERS PARSED: {len(tenders)}")
    return tenders

def manual_input_mode():
    """
    Mode input manual tradisional
    """
    print("📝 MANUAL INPUT MODE")
    print("=" * 50)
    print("Silakan paste data tender (tekan Ctrl+D setelah selesai):")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    text_content = "\n".join(lines)
    return parse_tender_data_smart(text_content)

def find_brave_browser():
    """
    Cari lokasi Brave Browser di Mac
    """
    possible_paths = [
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Brave Browser Nightly.app/Contents/MacOS/Brave Browser",
        os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Brave ditemukan: {path}")
            return path
    
    try:
        result = subprocess.run(["which", "brave-browser"], capture_output=True, text=True)
        if result.returncode == 0:
            brave_path = result.stdout.strip()
            print(f"✅ Brave ditemukan via command: {brave_path}")
            return brave_path
    except:
        pass
    
    print("❌ Brave Browser tidak ditemukan, menggunakan Chrome default")
    return None

def setup_brave_driver():
    """
    Setup Brave browser driver
    """
    print("🦁 Setting up Brave browser...")
    
    try:
        brave_path = find_brave_browser()
        
        chrome_options = Options()
        
        if brave_path:
            chrome_options.binary_location = brave_path
            print("✅ Using Brave Browser")
        else:
            print("⚠️  Using default Chrome")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-data-dir=./brave_session")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--remote-allow-origins=*")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✅ Browser driver ready")
        return driver
        
    except Exception as e:
        print(f"❌ Browser driver setup failed: {e}")
        return None

def copy_page_content(driver):
    """
    Smart copy content dari halaman web dengan Select All + Copy
    """
    print("📋 COPYING PAGE CONTENT...")
    
    try:
        # Method 1: Try to select all using body element
        body = driver.find_element(By.TAG_NAME, "body")
        
        # Clear any existing selection
        body.click()
        
        # Select all (Cmd+A on Mac, Ctrl+A on Windows/Linux)
        actions = ActionChains(driver)
        actions.key_down(Keys.COMMAND if os.name == 'posix' else Keys.CONTROL)
        actions.send_keys('a')
        actions.key_up(Keys.COMMAND if os.name == 'posix' else Keys.CONTROL)
        actions.perform()
        
        time.sleep(1)
        
        # Copy selection (Cmd+C on Mac, Ctrl+C on Windows/Linux)
        actions = ActionChains(driver)
        actions.key_down(Keys.COMMAND if os.name == 'posix' else Keys.CONTROL)
        actions.send_keys('c')
        actions.key_up(Keys.COMMAND if os.name == 'posix' else Keys.CONTROL)
        actions.perform()
        
        time.sleep(1)
        
        # Get content from clipboard
        copied_content = pyperclip.paste()
        
        if copied_content and len(copied_content) > 100:
            print(f"✅ Successfully copied {len(copied_content)} characters")
            return copied_content
        else:
            print("❌ Clipboard content too short, trying alternative method...")
            return None
            
    except Exception as e:
        print(f"❌ Copy method failed: {e}")
        return None

class BraveSessionManager:
    def __init__(self):
        self.driver = None
        
    def get_authenticated_session(self):
        """
        Dapatkan session yang terautentikasi
        """
        print("🦁 BRAVE BROWSER SESSION MANAGER")
        print("=" * 50)
        print("Pilih metode:")
        print("1. Smart Copy Mode (Select All + Copy dari browser)")
        print("2. Manual input saja")
        
        choice = input("Pilihan (1/2): ").strip()
        
        if choice == "2":
            print("📝 Switching to manual input mode...")
            return None, None
        else:
            return self.smart_copy_mode()
    
    def smart_copy_mode(self):
        """Mode Smart Copy dengan Select All + Copy"""
        print("🎯 SMART COPY MODE")
        print("-" * 45)
        print("Panduan:")
        print("1. Browser akan buka halaman tender")
        print("2. Login manual jika diperlukan") 
        print("3. Scroll ke bagian yang ingin di-copy")
        print("4. Kembali ke terminal dan tekan Enter")
        print("5. Program akan otomatis Select All + Copy")
        print("-" * 45)
        
        self.driver = setup_brave_driver()
        if not self.driver:
            print("❌ Failed to start browser, falling back to manual mode")
            return None, None
        
        try:
            # Buka halaman tender
            self.driver.get("https://tender-indonesia.com/Project_room/Index_info.php")
            print("✅ Browser opened to: https://tender-indonesia.com/Project_room/Index_info.php")
            print("💡 Silakan login dan scroll ke data yang ingin di-copy...")
            input("Press Enter ketika siap untuk copy content...")
            
            # Copy content dari halaman
            copied_content = copy_page_content(self.driver)
            
            if copied_content:
                print("📋 CONTENT COPIED SUCCESSFULLY!")
                print("🔄 Now parsing the copied content...")
                
                # Tampilkan preview content yang di-copy
                print(f"\n📄 COPIED CONTENT PREVIEW (first 500 chars):")
                print("-" * 50)
                print(copied_content[:500] + "..." if len(copied_content) > 500 else copied_content)
                print("-" * 50)
                
                # Parse content yang sudah di-copy
                tenders = parse_tender_data_smart(copied_content)
                return tenders, copied_content
            else:
                print("❌ Failed to copy content, using manual mode")
                return None, None
                
        except Exception as e:
            print(f"❌ Smart copy mode failed: {e}")
            return None, None
    
    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass

def main():
    """
    Main function dengan Smart Copy Mode
    """
    print("🚀 SMART TENDER EXTRACTOR - COPY/PASTE METHOD")
    print("=" * 60)
    
    session_manager = BraveSessionManager()
    all_tenders = []
    
    try:
        result, copied_content = session_manager.get_authenticated_session()
        
        if result is not None:
            # Smart copy mode mengembalikan list of tenders
            all_tenders = result
            print(f"✅ Smart copy berhasil! Ditemukan {len(all_tenders)} tender")
            
            # Tanya user apakah ingin menyimpan content yang di-copy
            if copied_content and len(all_tenders) == 0:
                print("\n⚠️  Tidak ada tender yang terdeteksi dalam content yang di-copy!")
                save_choice = input("Apakah ingin menyimpan content yang di-copy ke file untuk debugging? (y/n): ").strip().lower()
                if save_choice == 'y':
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = f'debug_copied_content_{timestamp}.txt'
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(copied_content)
                    print(f"💾 Debug content saved to: {debug_file}")
        else:
            print("\n📝 MANUAL MODE")
            all_tenders = manual_input_mode()
        
        # Process and save data
        if all_tenders:
            df = pd.DataFrame(all_tenders)
            df = df[['Sector', 'Client', 'Tanggal Rilis', 'SOW', 'Judul Tender']]
            df = df.drop_duplicates()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f'tender_data_{timestamp}.xlsx'
            df.to_excel(output_file, index=False, engine='openpyxl')
            
            print(f"\n💾 Data disimpan: {output_file}")
            print(f"📊 Total tender: {len(df)}")
            
            # Show sector distribution
            sector_stats = df['Sector'].value_counts()
            print(f"\n📂 DISTRIBUSI SECTOR:")
            for sector, count in sector_stats.items():
                print(f"   • {sector}: {count} tender")
            
            # Show sample
            print("\n📋 SAMPLE DATA:")
            for i, row in df.head(5).iterrows():
                print(f"{i+1}. {row['Sector']} | {row['Client']} | {row['Tanggal Rilis']}")
                print(f"   SOW: {row['SOW']}")
                print(f"   Judul: {row['Judul Tender'][:80]}...")
                print()
                
        else:
            print("❌ Tidak ada data tender yang ditemukan")
        
    finally:
        session_manager.cleanup()

if __name__ == "__main__":
    # Install pyperclip jika belum ada
    try:
        import pyperclip
    except ImportError:
        print("📦 Installing pyperclip...")
        subprocess.check_call(["pip", "install", "pyperclip"])
        import pyperclip
    
    main()