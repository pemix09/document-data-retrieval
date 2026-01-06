import os
import json
import pytesseract
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from langchain_ollama import OllamaLLM

# --- KONFIGURACJA ---
# Jeśli używasz Windows, podaj pełną ścieżkę do tesseract.exe
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

INPUT_DIR = "scans"
OUTPUT_ROOTS = ["content", "summary", "titles", "category", "type", "info"]
MODEL_NAME = "llama3" 

# Inicjalizacja LLM
llm = OllamaLLM(model=MODEL_NAME, temperature=0)

ALLOWED_TYPES = [
    "pit11", "pit37", "pit36", "pit36L", "pit28", "pit38", "pit39", "pit5", "pit8C",
    "vat7", "cit8", "pcc3", "invoice", "proformaInvoice", "receipt", "utilityBill",
    "bankStatement", "loanAgreement", "insurancePolicy", "notarialDeed", "courtJudgment",
    "powerOfAttorney", "employmentContract", "mandateContract", "taskContract", "b2bContract",
    "nonCompeteAgreement", "lawsuit", "idCard", "passport", "birthCertificate",
    "marriageCertificate", "deathCertificate", "peselConfirmation", "drivingLicense",
    "schoolCertificate", "universityDiploma", "professionalCertificate", "cv",
    "sickLeave", "prescription", "medicalResults", "referral", "medicalHistory",
    "vaccinationCard", "sanitaryBooklet", "propertyDeed", "landRegistry", "rentalAgreement",
    "registrationCertificate", "vehicleHistory", "landMap", "technicalInspection",
    "documentScan", "application", "certificate", "authorization", "other"
]

def perform_ocr(file_path):
    """Wyciąga tekst z obrazu lub PDF (polski + angielski)."""
    text = ""
    try:
        if file_path.suffix.lower() == ".pdf":
            pages = convert_from_path(file_path)
            for page in pages:
                text += pytesseract.image_to_string(page, lang='pol+eng')
        else:
            text = pytesseract.image_to_string(Image.open(file_path), lang='pol+eng')
    except Exception as e:
        print(f"  [!] Błąd OCR: {file_path.name}: {e}")
    return text

def analyze_text(text, hinted_type=None):
    """Analizuje tekst dokumentu, ignorując definicje i skupiając się na danych."""
    if not text.strip():
        return None

    hint_str = f"Sugerowany typ z folderu: {hinted_type}. " if hinted_type in ALLOWED_TYPES else ""

    prompt = f"""
    Działaj jako precyzyjny system ekstrakcji danych OCR. Wyciągnij informacje z poniższego tekstu.

    KATEGORYCZNE ZAKAZY (STRICT NEGATIVE CONSTRAINTS):
    1. NIE opisuj co to za dokument w teorii (np. "PIT to deklaracja...").
    2. NIE podawaj definicji prawnych ani urzędowych.
    3. NIE używaj fraz "Dokument ten służy do...", "Jest to formularz dla...".

    WYMAGANIA (STRICT RULES):
    1. "summary" MUSI zawierać wyłącznie fakty znalezione w tekście: konkretne IMIONA, NAZWISKA, NAZWY FIRM, DATY i KWOTY.
    2. Jeśli widzisz umowę, zacznij od: "Umowa zawarta dnia [Data] pomiędzy [Podmiot A] a [Podmiot B]".
    3. Tytuł i streszczenie napisz w języku, w którym jest dokument.

    STRUKTURA JSON:
    - "title": [Typ] - [Główny Podmiot] - [Data/Rok] (w języku dokumentu).
    - "summary": Konkretne streszczenie faktów (5-8 zdań) (w języku dokumentu).
    - "category": jedna z: financial, legal, personal, health, property, other.
    - "type": wybierz dokładnie jeden klucz: {", ".join(ALLOWED_TYPES)}.
    - "info": konkretna usługa (np. prąd, gaz) lub 'brak'.

    TEKST DO ANALIZY:
    {text}
    """
    
    try:
        response = llm.invoke(prompt)
        start, end = response.find('{'), response.rfind('}') + 1
        return json.loads(response[start:end])
    except Exception as e:
        print(f"  [!] Błąd AI: {e}")
        return None

def save_result(rel_path, data, raw_text):
    """Zapisuje wyniki, odtwarzając strukturę folderów wejściowych."""
    base_filename = rel_path.stem + ".txt"
    sub_dir = rel_path.parent

    # 1. Zapis surowego tekstu
    c_dir = Path("content") / sub_dir
    c_dir.mkdir(parents=True, exist_ok=True)
    with open(c_dir / base_filename, "w", encoding="utf-8") as f:
        f.write(raw_text)
    
    # 2. Zapis pól AI
    if data:
        mapping = {
            "titles": "title", "summary": "summary", "category": "category",
            "type": "type", "info": "info"
        }
        for root, key in mapping.items():
            target_dir = Path(root) / sub_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            content = str(data.get(key, "Brak danych"))
            with open(target_dir / base_filename, "w", encoding="utf-8") as f:
                f.write(content)

def main():
    input_root = Path(INPUT_DIR)
    if not input_root.exists():
        print(f"Folder '{INPUT_DIR}' nie istnieje!")
        return

    all_files = [f for f in input_root.rglob("*") if f.is_file() and f.suffix.lower() in [".pdf", ".jpg", ".png", ".jpeg"]]
    print(f"🚀 Rozpoczynam przetwarzanie {len(all_files)} plików (tryb rekurencyjny)...")
    
    for file_path in all_files:
        rel_path = file_path.relative_to(input_root)
        hinted_type = file_path.parent.name
        
        print(f"--- Przetwarzanie: {rel_path}")
        
        raw_text = perform_ocr(file_path)
        if raw_text.strip():
            analysis = analyze_text(raw_text, hinted_type=hinted_type)
            save_result(rel_path, analysis, raw_text)
            print(f"✅ Gotowe: {rel_path}")
        else:
            print(f"⚠️ Pominęto (pusty tekst): {rel_path}")

if __name__ == "__main__":
    main()