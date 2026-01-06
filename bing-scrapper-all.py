import os
import requests
from bs4 import BeautifulSoup
import json
import time
import random

# --- KONFIGURACJA ---
OUTPUT_DIR = "scan-candidates"
LIMIT = 20  # Liczba zdjęć na kategorię

# Agresywne zapytania nakierowane na wypełnione dokumenty
CATEGORIES = {
    # --- FINANCIAL ---
    "pit11": "PIT-11 przykład wypełnienia skan",
    "pit37": "PIT-37 wypełniony formularz dane",
    "pit36": "PIT-36 uzupełniony przykład",
    "pit36L": "PIT-36L wypełniony skan",
    "pit28": "PIT-28 wypełniona deklaracja",
    "pit38": "PIT-38 przykład uzupełniony",
    "pit39": "PIT-39 przykładowe dane",
    "pit5": "PIT-5 wypełniony formularz skan",
    "pit8C": "PIT-8C wypełniony dane",
    "vat7": "VAT-7 deklaracja wypełniona przykład",
    "cit8": "CIT-8 uzupełniony formularz",
    "pcc3": "PCC-3 wypełniony przykład",
    "invoice": "faktura vat wypełniona dane skan",
    "proformaInvoice": "faktura proforma uzupełniona dane",
    "receipt": "paragon fiskalny zdjęcie realne",
    "utilityBill": "rachunek za prąd uzupełniony dane",
    "bankStatement": "wyciąg bankowy realny przykład",
    "loanAgreement": "umowa pożyczki wypełniona dane",
    "insurancePolicy": "polisa ubezpieczeniowa wypełniona skan",

    # --- LEGAL ---
    "notarialDeed": "akt notarialny skan z danymi",
    "courtJudgment": "wyrok sądu wypełniony uzupełniony",
    "powerOfAttorney": "pełnomocnictwo uzupełnione dane",
    "employmentContract": "umowa o pracę wypełniona dane",
    "mandateContract": "umowa zlecenie uzupełniona przykładowa",
    "taskContract": "umowa o dzieło wypełniona skan",
    "b2bContract": "umowa B2B wypełniona dane",
    "nonCompeteAgreement": "zakaz konkurencji uzupełniony przykład",
    "lawsuit": "pozew cywilny wypełniony skan",

    # --- PERSONAL ---
    "idCard": "dowód osobisty specimen dane polska",
    "passport": "paszport polski specimen dane",
    "birthCertificate": "odpis aktu urodzenia wypełniony",
    "marriageCertificate": "akt małżeństwa uzupełniony dane",
    "deathCertificate": "akt zgonu wypełniony przykład",
    "peselConfirmation": "potwierdzenie nadania PESEL wypełnione",
    "drivingLicense": "prawo jazdy specimen polska",
    "schoolCertificate": "świadectwo szkolne wypełnione dane",
    "universityDiploma": "dyplom ukończenia studiów wypełniony",
    "professionalCertificate": "certyfikat zawodowy uzupełniony",
    "cv": "życiorys CV wypełniony dane",

    # --- HEALTH ---
    "sickLeave": "zwolnienie lekarskie L4 wypełnione skan",
    "prescription": "recepta lekarska wypisana dane",
    "medicalResults": "wyniki badań laboratoryjnych dane pacjenta",
    "referral": "skierowanie do lekarza uzupełnione",
    "medicalHistory": "karta pacjenta wypełniona skan",
    "vaccinationCard": "karta szczepień uzupełniona",
    "sanitaryBooklet": "książeczka sanepidowska wypełniona",

    # --- PROPERTY ---
    "propertyDeed": "akt własności nieruchomości uzupełniony",
    "landRegistry": "księga wieczysta odpis przykład",
    "rentalAgreement": "umowa najmu mieszkania wypełniona dane",
    "registrationCertificate": "dowód rejestracyjny pojazdu uzupełniony",
    "vehicleHistory": "raport historii pojazdu dane",
    "landMap": "mapa geodezyjna skan",
    "technicalInspection": "zaświadczenie o badaniu technicznym wypełnione",

    # --- OTHER ---
    "documentScan": "skan dokumentu z tekstem i pieczątką",
    "application": "wniosek urzędowy wypełniony skan",
    "certificate": "zaświadczenie o niekaralności uzupełnione",
    "authorization": "upoważnienie wypełnione dane",
    "other": "pismo urzędowe wypełnione skan"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def download_images(query, folder_name):
    print(f"\n🚀 POBIERANIE WYPEŁNIONYCH: {folder_name.upper()}")
    search_url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}&form=HDRSC2"
    
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        target_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(target_path, exist_ok=True)

        links = []
        for a in soup.find_all("a", {"class": "iusc"}):
            if "m" in a.attrs:
                m = json.loads(a["m"])
                links.append(m["murl"])

        print(f"  🔍 Linki: {len(links)}")
        
        downloaded = 0
        for url in links:
            if downloaded >= LIMIT: break
            try:
                if any(ext in url.lower() for ext in [".pdf", ".html", ".php"]): continue
                ext = ".jpg" if ".png" not in url.lower() else ".png"
                
                res = requests.get(url, headers=HEADERS, timeout=7)
                if res.status_code == 200 and "text/html" not in res.headers.get('Content-Type', ''):
                    file_name = f"{folder_name}_{downloaded}{ext}"
                    with open(os.path.join(target_path, file_name), "wb") as f:
                        f.write(res.content)
                    print(f"    ✅ [{downloaded+1}/{LIMIT}] {file_name}")
                    downloaded += 1
                    if downloaded % 5 == 0: time.sleep(1)
            except: continue

    except Exception as e:
        print(f"  🚨 Błąd: {e}")

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for i, (folder, query) in enumerate(CATEGORIES.items()):
        download_images(query, folder)
        wait = random.uniform(3, 6)
        print(f"😴 Przerwa {wait:.1f}s... ({i+1}/{len(CATEGORIES)})")
        time.sleep(wait)