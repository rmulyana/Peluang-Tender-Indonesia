import pandas as pd
import re
from datetime import datetime

def parse_tender_data(text_content):
    """
    Fungsi untuk parsing data tender dari text content - VERSION 2
    """
    # Convert tabs to spaces dan clean up
    text_content = text_content.replace('\t', ' ').replace('○', 'o').replace('•', 'o')
    
    lines = text_content.split('\n')
    tenders = []
    current_sector = ""
    current_client = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and placeholder data
        if not line or 'DALAM PROSES ENTRI DATA' in line:
            continue
            
        # Detect sector (ALL CAPS atau judul utama)
        if (re.match(r'^[A-Z&/\s]+$', line) and len(line) > 3 and 
            not any(word in line.lower() for word in ['government', 'kota', 'kabupaten'])):
            current_sector = line
            current_client = ""
            continue
            
        # Detect client (indented text, biasanya nama perusahaan/instansi)
        if (not line.startswith('o') and 
            not line.startswith('(') and
            not 'GOVERNMENT' in line and
            len(line) > 5 and
            not re.search(r'\d{4}-\d{2}-\d{2}', line)):
            
            # Skip jika ini adalah sub-heading government
            if not any(gov in line for gov in ['CENTRAL GOVERNMENT', 'PROVINCE GOVERNMENT', 
                                             'CITY GOVERNMENT', 'REGENCY GOVERNMENT', 'ALL GOVERNMENT']):
                current_client = line.strip()
            continue
            
        # Parse tender items dengan bullet points (o)
        if line.startswith('o') or re.search(r'\(\d{4}-\d{2}-\d{2}\)', line):
            # Clean the line
            line = re.sub(r'^o\s*', '', line)  # Remove bullet point
            line = re.sub(r'^\.\s*', '', line)  # Remove leading dot
            
            # Extract date
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)', line)
            if date_match:
                date = date_match.group(1)
                
                # Extract remaining text after date
                remaining_text = line[date_match.end():].strip()
                
                # Extract SOW (dalam kurung) dan Judul
                sow_match = re.search(r'\(([^)]+)\)', remaining_text)
                if sow_match:
                    sow = sow_match.group(1)
                    title = remaining_text[sow_match.end():].strip()
                    # Clean title
                    title = re.sub(r'^[-\s]*', '', title)
                else:
                    # Jika tidak ada SOW dalam kurung
                    sow = ""
                    title = remaining_text
                
                # Clean up
                sow = sow.strip()
                title = title.strip()
                
                # Remove trailing dots/dashes
                title = re.sub(r'^[\.\-\s]*', '', title)
                
                # Add to tenders list jika ada sector
                if current_sector:
                    tenders.append({
                        'Sector': current_sector,
                        'Client': current_client if current_client else 'Unknown',
                        'Tanggal Rilis': date,
                        'SOW': sow,
                        'Judul Tender': title
                    })
    
    return tenders

def manual_input_mode():
    """
    Mode input manual - paste data setiap kali
    """
    print("=" * 60)
    print("SCRIPT EXTRACT DATA TENDER - VERSION 2")
    print("=" * 60)
    print("\n📝 CARA PENGGUNAAN:")
    print("1. Buka website tender-indonesia.com")
    print("2. Copy semua data tender (Ctrl+A, Ctrl+C)")
    print("3. Paste di sini (Ctrl+V)")
    print("4. Ketika muncul warning, pilih 'OK' atau 'Convert tabs to spaces'")
    print("5. Tekan Enter 2 kali untuk memproses\n")
    
    print("➡️  Paste data di bawah ini (tekan Enter 2 kali setelah selesai):")
    print("-" * 50)
    
    lines = []
    print("Menunggu input...")
    
    try:
        while True:
            line = input()
            if line == "":
                # Check if we have multiple empty lines
                if lines and lines[-1] == "":
                    break
                lines.append(line)
            else:
                lines.append(line)
    except EOFError:
        pass
    except KeyboardInterrupt:
        print("\n❌ Proses dibatalkan")
        return []
    
    text_content = "\n".join(lines)
    return parse_tender_data(text_content)

def save_to_excel(tenders, filename):
    """
    Simpan data ke file Excel
    """
    if not tenders:
        print("❌ Tidak ada data untuk disimpan")
        return False
    
    df = pd.DataFrame(tenders)
    df = df[['Sector', 'Client', 'Tanggal Rilis', 'SOW', 'Judul Tender']]
    
    try:
        df.to_excel(filename, index=False, engine='openpyxl')
        return True
    except Exception as e:
        print(f"❌ Error menyimpan file: {e}")
        return False

def main():
    """
    Main function
    """
    print("🚀 Memulai ekstraksi data tender...\n")
    
    tenders = manual_input_mode()
    
    if tenders:
        print(f"\n✅ Berhasil mengekstrak {len(tenders)} data tender")
        
        # Preview
        print("\n📋 PREVIEW DATA (3 pertama):")
        print("-" * 100)
        for i, tender in enumerate(tenders[:3], 1):
            print(f"{i}. SECTOR: {tender['Sector']}")
            print(f"   CLIENT: {tender['Client']}")
            print(f"   DATE: {tender['Tanggal Rilis']}")
            print(f"   SOW: {tender['SOW']}")
            print(f"   JUDUL: {tender['Judul Tender']}")
            print()
        
        # Save to Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'tender_data_{timestamp}.xlsx'
        
        if save_to_excel(tenders, output_file):
            print(f"💾 Data berhasil disimpan ke: {output_file}")
            
            # Statistics
            sectors = set(t['Sector'] for t in tenders)
            clients = set(t['Client'] for t in tenders)
            print(f"\n📊 STATISTIK:")
            print(f"   • Sectors: {len(sectors)}")
            print(f"   • Clients: {len(clients)}")
            print(f"   • Tenders: {len(tenders)}")
            
            # Show all sectors and clients
            print(f"\n📂 Sectors ditemukan: {', '.join(sorted(sectors))}")
            print(f"👥 Clients ditemukan: {', '.join(sorted(clients)[:5])}..." if len(clients) > 5 else f"👥 Clients: {', '.join(sorted(clients))}")
            
    else:
        print("❌ Tidak ada data tender yang berhasil diekstrak")
        print("   Pastikan format data sesuai")

if __name__ == "__main__":
    main()