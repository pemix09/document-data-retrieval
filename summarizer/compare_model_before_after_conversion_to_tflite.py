import os
import torch
import numpy as np
import tensorflow as tf
import pytesseract
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# --- KONFIGURACJA ---
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

SUMMARIZER_DIR = Path(__file__).resolve().parent
BASE_DIR = SUMMARIZER_DIR.parent
PT_MODEL_PATH = SUMMARIZER_DIR / "models" / "flan_t5_custom"
TFLITE_MODEL_PATH = SUMMARIZER_DIR / "models" / "summarizer.tflite"
VERIFY_DIR = SUMMARIZER_DIR / "scans_to_verify_summary"

MAX_LEN = 256  # Musi być zgodne z ostatnią konwersją
device = "mps" if torch.backends.mps.is_available() else "cpu"


# --- ŁADOWANIE ---

def load_pt_model():
    print(f"🚀 Ładowanie modelu PyTorch z: {PT_MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(PT_MODEL_PATH)
    model = AutoModelForSeq2SeqLM.from_pretrained(PT_MODEL_PATH).to(device)
    return tokenizer, model


def load_tflite_model():
    print(f"🚀 Ładowanie modelu TFLite z: {TFLITE_MODEL_PATH}")
    interpreter = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH))
    interpreter.allocate_tensors()
    return interpreter


# --- GENEROWANIE ---

def generate_pytorch(prompt, tokenizer, model):
    inputs = tokenizer(prompt, return_tensors="pt", max_length=MAX_LEN, truncation=True).to(device)
    outputs = model.generate(**inputs, max_new_tokens=128, num_beams=1, do_sample=False)  # Greedy dla porównania
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def generate_tflite(prompt, interpreter, tokenizer):
    input_ids = tokenizer.encode(prompt, max_length=MAX_LEN, truncation=True, padding="max_length")
    input_ids = np.array([input_ids], dtype=np.int32)
    decoder_input_ids = np.zeros((1, MAX_LEN), dtype=np.int32)
    output_tokens = [0]

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    for i in range(MAX_LEN - 1):
        for j, token in enumerate(output_tokens):
            decoder_input_ids[0, j] = token

        # Dopasowanie tensorów po nazwach
        for detail in input_details:
            if "input_ids" in detail['name'] and "decoder" not in detail['name']:
                interpreter.set_tensor(detail['index'], input_ids)
            elif "decoder_input_ids" in detail['name']:
                interpreter.set_tensor(detail['index'], decoder_input_ids)

        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])

        # Pobieramy logity dla aktualnej pozycji
        next_token_logits = output_data[0, len(output_tokens) - 1, :]
        next_token = int(np.argmax(next_token_logits))

        if next_token == 1: break
        output_tokens.append(next_token)
        if len(output_tokens) >= 128: break  # Limit bezpieczeństwa

    return tokenizer.decode(output_tokens, skip_special_tokens=True)


# --- OCR ---

def perform_ocr(file_path):
    try:
        if file_path.suffix.lower() == ".pdf":
            pages = convert_from_path(file_path)
            return "".join([pytesseract.image_to_string(p, lang='pol+eng') for p in pages])
        return pytesseract.image_to_string(Image.open(file_path), lang='pol+eng')
    except Exception as e:
        return f"Błąd OCR: {e}"


# --- MAIN ---

def main():
    tokenizer, pt_model = load_pt_model()
    tflite_interpreter = load_tflite_model()

    files = [f for f in VERIFY_DIR.glob("*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".pdf"]]
    if not files:
        print(f"ℹ️ Brak plików w {VERIFY_DIR}")
        return

    for file_path in files:
        print(f"\n" + "█" * 60)
        print(f"📄 PLIK: {file_path.name}")
        ocr_text = perform_ocr(file_path).strip()

        for task in ["headline", "summarize"]:
            prompt = f"{task}: {ocr_text}"
            print(f"\n🔍 ZADANIE: {task.upper()}")

            # Wynik PyTorch
            pt_res = generate_pytorch(prompt, tokenizer, pt_model)
            # Wynik TFLite
            tfl_res = generate_tflite(prompt, tflite_interpreter, tokenizer)

            print(f"{'PyTorch:':<10} {pt_res}")
            print(f"{'TFLite:':<10} {tfl_res}")

            # Prosta weryfikacja zgodności
            if pt_res.strip() == tfl_res.strip():
                print("✅ ZGODNOŚĆ: 100%")
            else:
                print("⚠️ ROZBIEŻNOŚĆ WYKRYTA")


if __name__ == "__main__":
    main()