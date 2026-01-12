import os
import json
import pytesseract
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from langchain_ollama import OllamaLLM

# --- KONFIGURACJA ---
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

# Folder wejściowy
INPUT_DIR = "scans"
HISTORY_FILE = "processed_real_scans_files.txt"  # Plik z listą zrobionych skanów
MODEL_NAME = "llama3"

# Definicja języków
TARGET_LANGUAGES = {
    "pl": "Polish",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "uk": "Ukrainian"
}

llm = OllamaLLM(model=MODEL_NAME, temperature=0)

# NOWA, SKONSOLIDOWANA LISTA TYPÓW (zgodna z nowym Enumem)
ALLOWED_TYPES = [
    # Financial
    "taxDocument", "invoice", "receipt", "utilityBill", "bankStatement",
    "loanAgreement", "insurancePolicy",

    # Legal
    "notarialDeed", "courtDocument", "powerOfAttorney", "contract",

    # Personal
    "idCard", "passport", "birthCertificate", "marriageCertificate",
    "deathCertificate", "officialCertificate", "drivingLicense",
    "educationDocument", "cv",

    # Health
    "medicalDocument", "prescription", "referral", "vaccinationCard",
    "sanitaryBooklet",

    # Property
    "propertyDeed", "rentalAgreement", "vehicleDocument", "technicalInspection",

    # Other
    "documentScan", "application", "certificate", "other"
]


# --- OBSŁUGA HISTORII (RESUME) ---
def load_history():
    """Wczytuje listę przetworzonych plików do setu (dla szybkiego wyszukiwania)."""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def mark_as_done(rel_path):
    """Dopisuje plik do historii."""
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{rel_path}\n")


# --- OCR I LLM ---
def perform_ocr(file_path):
    text = ""
    try:
        langs = 'pol+eng'
        if file_path.suffix.lower() == ".pdf":
            pages = convert_from_path(file_path)
            for page in pages:
                text += pytesseract.image_to_string(page, lang=langs)
        else:
            text = pytesseract.image_to_string(Image.open(file_path), lang=langs)
    except Exception as e:
        print(f"  [!] Błąd OCR: {file_path.name}: {e}")
    return text


def ask_llm_json(prompt):
    try:
        response = llm.invoke(prompt)
        clean = response.replace("```json", "").replace("```", "").strip()
        start, end = clean.find('{'), clean.rfind('}') + 1
        return json.loads(clean[start:end])
    except Exception:
        return None


def ask_llm_text(prompt):
    try:
        response = llm.invoke(prompt)
        return response.strip().strip('"').strip("'")
    except Exception:
        return "Translation Error"


# --- LOGIKA PRZETWARZANIA ---
def get_core_metadata(text, hinted_type=None):
    print("   🧠 Analiza struktury dokumentu (Core Metadata)...")

    # Jeśli folder sugeruje typ, przekaż go jako wskazówkę
    hint_str = ""
    if hinted_type in ALLOWED_TYPES:
        hint_str = f"Strong Hint: The document is likely located in folder '{hinted_type}'."

    prompt = f"""
    Analyze the following document text.
    {hint_str}

    Extract structured data.
    RULES:
    1. 'summary_base': Write a factual summary in ENGLISH (5 sentences).
    2. 'title_base': Write a title in ENGLISH format: "[Specific Type] - [Entity] - [Date]". 
       (e.g., "Tax Document (PIT-11) - Employer Name - 2023")
    3. 'category': Must be one of: financial, legal, personal, health, property, other.
    4. 'type': Choose the BEST MATCH from this specific list: {", ".join(ALLOWED_TYPES)}.
    5. 'info': Specific details (e.g. "PIT-11", "Umowa o pracę", "Prąd").

    Return ONLY JSON:
    {{
        "title_base": "...",
        "summary_base": "...",
        "category": "...",
        "type": "...",
        "info": "..."
    }}

    TEXT:
    {text[:4000]} 
    """
    return ask_llm_json(prompt)


def translate_section(text, target_lang, content_type="text"):
    prompt = f"""
    Translate the following {content_type} into {target_lang}.
    Output ONLY the translation. No explanations. No markdown.

    TEXT TO TRANSLATE:
    {text}
    """
    return ask_llm_text(prompt)


def save_file(root_folder, lang_code, sub_dir, filename, content):
    path = Path(root_folder) / lang_code / sub_dir
    path.mkdir(parents=True, exist_ok=True)
    with open(path / filename, "w", encoding="utf-8") as f:
        f.write(str(content))


def save_meta(root_folder, sub_dir, filename, content):
    path = Path(root_folder) / sub_dir
    path.mkdir(parents=True, exist_ok=True)
    with open(path / filename, "w", encoding="utf-8") as f:
        f.write(str(content))


def process_file(file_path, input_root):
    rel_path = file_path.relative_to(input_root)
    rel_path_str = str(rel_path)  # Klucz do pliku historii

    base_filename = rel_path.stem + ".txt"
    sub_dir = rel_path.parent
    hinted_type = sub_dir.name if sub_dir.name != input_root.name else None

    # 1. OCR
    raw_text = perform_ocr(file_path)

    if not raw_text.strip():
        print("   ⚠️ Pusty OCR - oznaczam jako przetworzony (bez wyników).")
        mark_as_done(rel_path_str)
        return

    # Zapisz oryginał (Content) - to zostaje, bo to dane wejściowe
    save_meta("content", sub_dir, base_filename, raw_text)

    # 2. Analiza podstawowa (Core)
    core_data = get_core_metadata(raw_text, hinted_type)

    if not core_data:
        print("   ❌ Błąd analizy AI. Przerywam dla tego pliku.")
        return

    # Zapisz dane niezależne od języka
    save_meta("category", sub_dir, base_filename, core_data.get("category", "other"))
    save_meta("type", sub_dir, base_filename, core_data.get("type", "other"))
    save_meta("info", sub_dir, base_filename, core_data.get("info", "none"))

    base_title = core_data.get("title_base", "Document")
    base_summary = core_data.get("summary_base", "No summary.")

    # 3. Pętla Tłumaczeń (TYLKO ETYKIETY)
    print("   🌍 Rozpoczynam generowanie etykiet (tytuły/podsumowania)...")

    for code, lang_name in TARGET_LANGUAGES.items():
        print(f"      -> [{code.upper()}] {lang_name}...", end="", flush=True)

        # A. Tytuł
        if code == "en":
            final_title = base_title
        else:
            final_title = translate_section(base_title, lang_name, "title")
        save_file("titles", code, sub_dir, base_filename, final_title)

        # B. Streszczenie
        if code == "en":
            final_summary = base_summary
        else:
            final_summary = translate_section(base_summary, lang_name, "summary")
        save_file("summary", code, sub_dir, base_filename, final_summary)

        # C. Pełna treść - USUNIĘTO (Oszczędność czasu i tokenów)
        
        print(" OK.")

    # SUKCES! Dopiero tutaj zapisujemy do historii
    print(f"✅ Zakończono: {file_path.name}")
    mark_as_done(rel_path_str)


def main():
    input_root = Path(INPUT_DIR)
    if not input_root.exists():
        print(f"Brak folderu wejściowego: {INPUT_DIR}")
        return

    # Wczytaj historię
    processed_files = load_history()
    print(f"📂 Załadowano historię: {len(processed_files)} plików już przetworzonych.")

    all_files = [f for f in input_root.rglob("*") if
                 f.is_file() and f.suffix.lower() in [".pdf", ".jpg", ".png", ".jpeg"]]
    print(f"🚀 Znaleziono łącznie {len(all_files)} plików do analizy.")

    for f in all_files:
        rel_path_str = str(f.relative_to(input_root))

        # Sprawdzenie w historii
        if rel_path_str in processed_files:
            print(f"⏩ Pomijam (już w historii): {rel_path_str}")
            continue

        print(f"\n📄 Przetwarzanie: {rel_path_str}")
        try:
            process_file(f, input_root)
        except KeyboardInterrupt:
            print("\n🛑 Zatrzymano przez użytkownika. Postęp zapisany.")
            break
        except Exception as e:
            print(f"\n❌ Krytyczny błąd dla {rel_path_str}: {e}")


if __name__ == "__main__":
    main()