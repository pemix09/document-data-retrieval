import os
import torch
import pytesseract
import json
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# --- KONFIGURACJA ---
# Ścieżka do Tesseracta (zgodnie z Twoim systemem)
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

# Ścieżki relatywne
SUMMARIZER_DIR = Path(__file__).resolve().parent
BASE_DIR = SUMMARIZER_DIR.parent
MODEL_PATH = SUMMARIZER_DIR / "models" / "flan_t5_custom"
VERIFY_DIR = SUMMARIZER_DIR / "scans_to_verify_summary"

# Urządzenie (wykryte mps w Twoich logach)
device = "mps" if torch.backends.mps.is_available() else "cpu"


def perform_ocr(file_path):
    """Konwertuje obraz/PDF na tekst."""
    text = ""
    try:
        if file_path.suffix.lower() == ".pdf":
            pages = convert_from_path(file_path)
            for page in pages:
                text += pytesseract.image_to_string(page, lang='pol+eng')
        else:
            text = pytesseract.image_to_string(Image.open(file_path), lang='pol+eng')
    except Exception as e:
        print(f"  [!] Błąd OCR dla {file_path.name}: {e}")
    return text


def load_model():
    print(f"🚀 Ładowanie modelu z: {MODEL_PATH}...")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"❌ Nie znaleziono modelu w {MODEL_PATH}.")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH).to(device)

    # --- DEBUG TOKENIZERA ---
    print("\n" + "=" * 40)
    print("🔍 TOKENIZER VERIFICATION (Dla porównania z Flutterem)")

    for word in ["Janina", "Joanna"]:
        encoded = tokenizer.encode(word, add_special_tokens=False)
        print(f"  ID dla słowa '{word}': {encoded}")

    # Dodatkowy test na dekodowanie
    test_ids = [0, 2664, 15, 1]  # Przykładowe ID
    decoded = tokenizer.decode(test_ids)
    print(f"  Test dekodowania {test_ids}: '{decoded}'")
    print("=" * 40 + "\n")
    # -----------------------

    return tokenizer, model


def generate_text(prompt, tokenizer, model):
    # Logowanie długości inputu
    inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True).to(device)
    input_len = inputs['input_ids'].shape[1]

    outputs = model.generate(
        **inputs,
        max_new_tokens=128,
        num_beams=4,
        early_stopping=True
    )

    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result, input_len


def main():
    tokenizer, model = load_model()

    if not VERIFY_DIR.exists():
        os.makedirs(VERIFY_DIR)
        print(f"📁 Folder {VERIFY_DIR} był pusty. Wrzuć tam zdjęcia dokumentów i uruchom ponownie.")
        return

    # Szukamy plików graficznych i PDF
    extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    files = [f for f in VERIFY_DIR.glob("*") if f.suffix.lower() in extensions]

    if not files:
        print(f"ℹ️ Brak obrazów lub plików PDF w {VERIFY_DIR}.")
        return

    print(f"🔍 Znaleziono {len(files)} dokumentów do weryfikacji.\n")

    for file_path in files:
        print(f"📄 PRZETWARZANIE: {file_path.name}")
        print("⏳ Wykonywanie OCR...")

        ocr_text = perform_ocr(file_path)

        if not ocr_text.strip():
            print(f"⚠️ Nie udało się odczytać tekstu z {file_path.name}. Pomijam.")
            continue

        print(f"📊 Długość tekstu OCR: {len(ocr_text)} znaków")
        print(f"📝 Pierwsze 100 znaków OCR: {ocr_text[:100].replace('\n', ' ')}...")
        print("-" * 30)

        # Zadanie 1: Tytuł
        title, t_len = generate_text(f"headline: {ocr_text}", tokenizer, model)
        print(f"📌 TYTUŁ (Tokeny wejściowe: {t_len}):\n{title}\n")

        # Zadanie 2: Streszczenie
        summary, s_len = generate_text(f"summarize: {ocr_text}", tokenizer, model)
        print(f"📝 STRESZCZENIE (Tokeny wejściowe: {s_len}):\n{summary}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()