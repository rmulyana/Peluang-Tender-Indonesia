# Tender Indonesia Scraper

A smart web scraper for extracting tender information from Tender Indonesia website.

## Features

- 🦁 Brave Browser automation with manual login
- 📋 Smart copy-paste method for reliable data extraction
- 🔧 Flexible parsing for various data formats
- 💾 Excel export with organized data
- 🎯 Sector-based classification
- 🔍 Debug mode for troubleshooting

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/tender-indonesia-scraper.git
cd tender-indonesia-scraper
Install dependencies:

bash
pip install -r requirements.txt
Make sure you have Brave Browser installed, or it will use Chrome as fallback.

Usage
Run the main script:

bash
python tender_hybrid.py
Interactive Options
The script provides two main modes:

1. Smart Copy Mode (Recommended)
Automatically opens Brave Browser to the tender page

You login manually and navigate to desired data

Script performs Select All + Copy automatically

Parses the copied content intelligently

Most reliable method

2. Manual Input Mode
Paste tender data directly into terminal

Useful when browser automation fails

Same parsing engine as smart copy mode

Output
The script generates Excel files (tender_data_YYYYMMDD_HHMMSS.xlsx) with the following columns:

Column	Description
Sector	Industry sector (OIL & GAS, GOVERNMENT, ELECTRICITY, etc.)
Client	Company or institution name
Tanggal Rilis	Tender release date (YYYY-MM-DD)
SOW	Scope of Work
Judul Tender	Tender title
Supported Data Formats
The parser handles various tender format variations:

o (2025-11-10) (SOW) Judul Tender

o (2025-11-10) (SOW) ) Judul Tender

o (2025-11-10) (SOW Judul Tender

(2025-11-10) (SOW) Judul Tender (without o)

Sector Classification
Automatic sector detection based on client names:

OIL & GAS: Pertamina, Petrochina, Shell, etc.

GOVERNMENT: Kementerian, Badan, Provinsi, Kota, Kabupaten

ELECTRICITY: PLN, Dongfang, Power, Listrik

MINING / CEMENT: Mining, Tambang, Coal, Batubara

BANK AND FINANCIAL SERVICE: Bank, Finance, Asuransi

OTHER PRIVATE SECTOR: All other companies

File Structure
text
tender-indonesia-scraper/
├── tender_hybrid.py          # Main scraper script
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── .gitignore              # Git ignore rules
Dependencies
selenium - Browser automation

pandas - Data manipulation and Excel export

openpyxl - Excel file handling

beautifulsoup4 - HTML parsing (fallback)

pyperclip - Clipboard access for smart copy

Troubleshooting
Common Issues
Browser not found: Install Brave Browser or Chrome

Login required: Manual login needed for the website

No tenders parsed: Check if data format matches expected patterns

Clipboard issues: Ensure pyperclip is installed and working

Debug Mode
The script includes detailed debug output. If parsing fails:

Check the debug messages in terminal

Verify the copied content contains tender data in expected format

Use manual input mode as fallback

Disclaimer
This tool is for educational and personal use only. Please:

Respect the website's terms of service

Check robots.txt before scraping

Be mindful of request frequency

Use responsibly and ethically

License
MIT License - feel free to modify and distribute.

Contributing
Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

text

You can now copy this entire content and save it as `README.md` in your project folder. The file is ready to be committed and pushed to your GitHub repository.
```
