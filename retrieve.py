import os
import json
from pathlib import Path
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from langchain_ollama import OllamaLLM

# --- KONFIGURACJA ---
# Upewnij się, że masz zainstalowane pakiety tesseract-ocr-pol i tesseract-ocr-eng
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
INPUT_DIR = "scans"
OUTPUT_ROOTS = ["content", "summary", "titles", "category", "type", "info"]
MODEL_NAME = "llama3" 

# Inicjalizacja LLM
llm = OllamaLLM(model=MODEL_NAME, temperature=0)

def perform_ocr(file_path):
    """Wyciąga tekst z obrazu lub pliku PDF (obsługa polskiego i angielskiego)."""
    text = ""
    try:
        # 'pol+eng' pozwala tesseractowi lepiej radzić sobie z dokumentami wielojęzycznymi
        config = '--l 10' # opcjonalnie ograniczenie czasu na stronę
        if file_path.suffix.lower() == ".pdf":
            pages = convert_from_path(file_path)
            for page in pages:
                text += pytesseract.image_to_string(page, lang='pol+eng')
        else:
            text = pytesseract.image_to_string(Image.open(file_path), lang='pol+eng')
    except Exception as e:
        print(f"Błąd OCR dla {file_path.name}: {e}")
    return text

def analyze_text(text, hinted_type=None):
    """Analizuje tekst dokumentu, zachowując język oryginału dla pól tekstowych."""
    if not text.strip():
        return None

    allowed_types = [
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

    hint_str = f"PODPOWIEDŹ: Folder sugeruje typ: {hinted_type}. " if hinted_type in allowed_types else ""

    prompt = f"""
    Przeanalizuj tekst dokumentu i zwróć wynik WYŁĄCZNIE w formacie JSON.
    {hint_str}
    
    ZASADY DOTYCZĄCE JĘZYKA:
    1. Zidentyfikuj język, w którym napisany jest dokument.
    2. Pola "title" oraz "summary" MUSZĄ być napisane w tym samym języku, co dokument (np. dokument po angielsku = tytuł i streszczenie po angielsku).
    3. Pola "category", "type" oraz "info" pozostają technicznymi kluczami (nie tłumacz ich).

    WYMAGANIA DLA PÓL JSON:
    - "title": [Typ dokumentu] - [Główne Podmioty] - [Data] (W JĘZYKU DOKUMENTU).
    - "summary": Rozbudowane streszczenie (5-8 zdań) (W JĘZYKU DOKUMENTU). Zawrzyj kto, z kim, jaki jest przedmiot i kwoty.
    - "category": financial, legal, personal, health, property, other.
    - "type": wybierz klucz: {", ".join(allowed_types)}.
    - "info": konkretna usługa lub 'brak'.

    TEKST:
    {text}
    """
    
    try:
        response = llm.invoke(prompt)
        start = response.find('{')
        end = response.rfind('}') + 1
        return json.loads(response[start:end])
    except Exception as e:
        print(f"Błąd analizy AI: {e}")
        return None
    
def save_result(rel_path, data, raw_text):
    """Zapisuje wyniki, odtwarzając strukturę folderów."""
    base_filename = rel_path.stem + ".txt"
    sub_dir = rel_path.parent

    # 1. OCR Content
    content_dir = Path("content") / sub_dir
    content_dir.mkdir(parents=True, exist_ok=True)
    with open(content_dir / base_filename, "w", encoding="utf-8") as f:
        f.write(raw_text)
    
    # 2. AI Metadata
    if data:
        mapping = {
            "titles": "title",
            "summary": "summary",
            "category": "category",
            "type": "type",
            "info": "info"
        }
        for folder_root, json_key in mapping.items():
            target_dir = Path(folder_root) / sub_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            
            content = str(data.get(json_key, ""))
            with open(target_dir / base_filename, "w", encoding="utf-8") as f:
                f.write(content)

def main():
    input_root = Path(INPUT_DIR)
    if not input_root.exists():
        print(f"Folder {INPUT_DIR} nie istnieje!")
        return

    all_files = [f for f in input_root.rglob("*") if f.is_file() and f.suffix.lower() in [".pdf", ".jpg", ".png", ".jpeg"]]
    
    print(f"🚀 Rozpoczynam przetwarzanie {len(all_files)} plików...")
    
    for file_path in all_files:
        rel_path = file_path.relative_to(input_root)
        hinted_type = file_path.parent.name
        
        print(f"--- Przetwarzanie: {rel_path}")
        
        raw_text = perform_ocr(file_path)
        if raw_text.strip():
            analysis = analyze_text(raw_text, hinted_type=hinted_type)
            save_result(rel_path, analysis, raw_text)
            print(f"✅ Sukces: {rel_path}")
        else:
            print(f"⚠️ Pominęto (brak tekstu): {rel_path}")

if __name__ == "__main__":
    main()