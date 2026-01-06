import os
import requests

# Folder docelowy
OUTPUT_DIR = "scan-candidates"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Lista sprawdzonych linków do polskich dokumentów (PDF/JPG)
DIRECT_LINKS = {
    "pit11": "https://www.podatki.gov.pl/media/6497/pit-11-27-v1-0e.pdf",
    "pit37": "https://www.podatki.gov.pl/media/8563/pit-37-28-v1-0e.pdf",
    "faktura": "https://ksiegowosc.infor.pl/wizualizacja-faktury-przyklad.jpg",
    "umowa_praca": "https://poradnikprzedsiebiorcy.pl/pliki/umowa-o-prace-wzor.pdf",
    "cv": "https://files.cvmkr.com/pl/examples/standard/cv-example-standard.png"
}

def download_sample():
    for name, url in DIRECT_LINKS.items():
        print(f"Pobieranie {name}...")
        try:
            r = requests.get(url, timeout=15)
            ext = ".pdf" if "pdf" in url else ".jpg"
            if ".png" in url: ext = ".png"
            
            with open(f"{OUTPUT_DIR}/{name}{ext}", "wb") as f:
                f.write(r.content)
            print(f"  ✅ Sukces")
        except Exception as e:
            print(f"  ❌ Błąd: {e}")

if __name__ == "__main__":
    download_sample()