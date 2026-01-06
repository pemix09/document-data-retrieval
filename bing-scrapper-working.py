import os
import requests
from bs4 import BeautifulSoup
import re
import json

# --- KONFIGURACJA ---
OUTPUT_DIR = "scan-candidates"
LIMIT = 3 # ile obrazów na każdą kategorię

CATEGORIES = {
    "pit11": "PIT-11 wypełniony wzór skan",
    "pit37": "PIT-37 wypełniony przykład",
    "invoice": "faktura vat wzór wypełniona",
    "employmentContract": "umowa o pracę wzór wypełniony",
    "cv": "cv wzór wypełniony pl"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
}

def download_images(query, folder_name):
    print(f"🔎 Szukam obrazów dla: {query}...")
    search_url = f"https://www.bing.com/images/search?q={query}"
    
    response = requests.get(search_url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Tworzenie folderu
    target_path = os.path.join(OUTPUT_DIR, folder_name)
    os.makedirs(target_path, exist_ok=True)

    # Bing przechowuje dane obrazów w atrybutach m (metadata)
    links = []
    for a in soup.find_all("a", {"class": "iusc"}):
        m = json.loads(a["m"])
        links.append(m["murl"]) # murl to link bezpośredni do obrazka

    count = 0
    for url in links[:LIMIT]:
        try:
            print(f"  -> Pobieram: {url[:60]}...")
            img_data = requests.get(url, timeout=10).content
            
            # Wykrywanie rozszerzenia z URL
            ext = ".jpg"
            if ".png" in url.lower(): ext = ".png"
            
            file_name = f"{folder_name}_{count}{ext}"
            with open(os.path.join(target_path, file_name), "wb") as f:
                f.write(img_data)
            count += 1
        except Exception as e:
            print(f"  ❌ Błąd przy {url}: {e}")

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for folder, query in CATEGORIES.items():
        download_images(query, folder)
    print("\n✅ Gotowe! Sprawdź folder 'scan-candidates'.")