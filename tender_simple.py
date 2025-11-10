import pandas as pd
import re
from datetime import datetime

def parse_tender_data(text_content):
    """
    Fungsi parsing yang lebih sederhana dan akurat
    """
    lines = text_content.split('\n')
    tenders = []
    current_sector = ""
    current_client = ""
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and placeholder data
        if not line or 'DALAM PROSES ENTRI DATA' in line:
            i += 1
            continue
        
        # 1. DETECT SECTOR (OIL & GAS, ELECTRICITY, dll)
        if (line in ['OIL & GAS', 'ELECTRICITY', 'INFRASTRUCTURE', 'MINING / CEMENT', 
                    'PLANTATION', 'BANK AND FINANCIAL SERVICE', 'MANUFACTURE', 
                    'TELECOMMUNICATION', 'HOSPITAL', 'INTERNATIONAL', 'OTHER PRIVATE SECTOR'] or
            'GOVERNMENT' in line or 'GOVERMENT' in line):
            current_sector = line
            current_client = ""
            i += 1
            continue
        
        # 2. DETECT CLIENT (baris setelah sector, biasanya perusahaan/instansi)
        if (current_sector and not current_client and 
            not line.startswith('o') and 
            not line.startswith('(') and
            not line.startswith('.') and
            len(line) > 3 and
            not re.search(r'\d{4}-\d{2}-\d{2}', line)):
            
            # Skip jika ini adalah sub-category government
            if not any(gov in line for gov in ['CENTRAL', 'PROVINCE', 'CITY', 'REGENCY', 'ALL']):
                current_client = line
            i += 1
            continue
        
        # 3. PARSE TENDER ITEMS
        if line.startswith('o') or line.startswith('.') or '(' in line:
            # Clean the line
            clean_line = re.sub(r'^[o\.]\s*', '', line)
            
            # Extract date
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)', clean_line)
            if date_match:
                date = date_match.group(1)
                
                # Get text after date
                after_date = clean_line[date_match.end():].strip()
                
                # Extract SOW (everything in parentheses after date)
                sow = ""
                title = after_date
                
                # Look for SOW in parentheses
                sow_match = re.search(r'\(\s*([^)]+)\s*\)', after_date)
                if sow_match:
                    sow = sow_match.group(1)
                    # Title is everything after the SOW parentheses
                    title = after_date[sow_match.end():].strip()
                    # Clean title - remove any leading punctuation
                    title = re.sub(r'^[\s\.\-\)]*', '', title)
                
                # Final cleanup
                sow = sow.strip()
                title = title.strip()
                
                # Add to tenders
                if current_sector and title:
                    tenders.append({
                        'Sector': current_sector,
                        'Client': current_client if current_client else 'Tidak Diketahui',
                        'Tanggal Rilis': date,
                        'SOW': sow,
                        'Judul Tender': title
                    })
        
        i += 1
    
    return tenders

def debug_parse_tender_data(text_content):
    """
    Fungsi untuk debugging - lihat proses parsing
    """
    print("🔍 DEBUG MODE - Proses Parsing:")
    print("=" * 80)
    
    lines = text_content.split('\n')
    current_sector = ""
    current_client = ""
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        print(f"Line {i:2d}: {line}")
        
        # Detect sector
        if (line in ['OIL & GAS', 'ELECTRICITY'] or 'GOVERNMENT' in line or 'GOVERMENT' in line):
            current_sector = line
            current_client = ""
            print(f"   → SECTOR: {current_sector}")
        
        # Detect client
        elif (current_sector and not current_client and 
              not line.startswith('o') and not line.startswith('(') and
              not re.search(r'\d{4}-\d{2}-\d{2}', line) and len(line) > 3):
            current_client = line
            print(f"   → CLIENT: {current_client}")
        
        # Parse tender
        elif line.startswith('o') or '(' in line:
            print(f"   → TENDER: {line}")
    
    print("=" * 80)

def mac_input_mode():
    """
    Mode input untuk Mac
    """
    print("=" * 60)
    print("TENDER EXTRACTOR - SIMPLE & ACCURATE VERSION")
    print("=" * 60)
    print("CARA PAKAI:")
    print("1. Paste data tender di bawah ini")
    print("2. Setelah selesai paste, tekan: Ctrl + D")
    print("-" * 60)
    print("Silakan paste data:")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    text_content = "\n".join(lines)
    
    # Tampilkan debug info
    debug_parse_tender_data(text_content)
    
    return parse_tender_data(text_content)

def main():
    """
    Main function
    """
    print("🚀 Memulai ekstraksi data tender...")
    
    tenders = mac_input_mode()
    
    if tenders:
        print(f"\n✅ SUKSES: Ditemukan {len(tenders)} tender!")
        
        # Buat DataFrame
        df = pd.DataFrame(tenders)
        df = df[['Sector', 'Client', 'Tanggal Rilis', 'SOW', 'Judul Tender']]
        
        # Simpan ke Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'tender_data_{timestamp}.xlsx'
        df.to_excel(output_file, index=False, engine='openpyxl')
        
        print(f"💾 File disimpan: {output_file}")
        
        # Tampilkan preview
        print("\n📋 PREVIEW DATA:")
        print("=" * 120)
        for i, tender in enumerate(tenders[:10], 1):
            print(f"{i:2d}. {tender['Sector']:20} | {tender['Client']:30} | {tender['Tanggal Rilis']} | {tender['SOW']:40} | {tender['Judul Tender'][:50]}...")
        
        # Statistik
        print(f"\n📊 STATISTIK:")
        print(f"   • Total Tenders: {len(tenders)}")
        
        # Tampilkan per sector
        sector_count = {}
        for tender in tenders:
            sector = tender['Sector']
            sector_count[sector] = sector_count.get(sector, 0) + 1
        
        print(f"   • Distribusi per Sector:")
        for sector, count in sector_count.items():
            print(f"      - {sector}: {count} tender")
            
    else:
        print("❌ Tidak ada data yang berhasil diproses.")

if __name__ == "__main__":
    main()