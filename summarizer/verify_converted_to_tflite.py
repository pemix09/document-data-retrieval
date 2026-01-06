import numpy as np
import tensorflow as tf
from transformers import AutoTokenizer
from pathlib import Path

# --- KONFIGURACJA ---
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "summarizer" / "models" / "summarizer.tflite"
TOKENIZER_DIR = BASE_DIR / "summarizer" / "models" / "flan_t5_custom"

# Te wartości muszą być zgodne z tymi, które ustawiliśmy podczas konwersji (256)
MAX_LEN = 256


def generate_tflite(prompt, interpreter, tokenizer):
    # 1. Tokenizacja wejścia (Enkoder)
    input_ids = tokenizer.encode(prompt, max_length=MAX_LEN, truncation=True, padding="max_length")
    input_ids = np.array([input_ids], dtype=np.int32)

    # 2. Przygotowanie wejścia dla Dekodera (zaczynamy od tokena PAD/START = 0)
    decoder_input_ids = np.zeros((1, MAX_LEN), dtype=np.int32)
    output_tokens = [0]

    # Pobranie szczegółów tensorów wejściowych i wyjściowych
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Logika generowania (identyczna jak we Flutterze)
    generated_text = ""
    print(f"⏳ Generowanie dla promptu: '{prompt[:30]}...'")

    for i in range(MAX_LEN - 1):
        # Wypełniamy decoder_input_ids dotychczasowymi tokenami
        for j, token in enumerate(output_tokens):
            decoder_input_ids[0, j] = token

        # Uruchomienie interpretera
        # Uwaga: kolejność zależy od tego, jak model został zapisany
        # Sprawdzamy nazwy tensorów, aby dopasować dane
        for detail in input_details:
            if "input_ids" in detail['name'] and "decoder" not in detail['name']:
                interpreter.set_tensor(detail['index'], input_ids)
            elif "decoder_input_ids" in detail['name']:
                interpreter.set_tensor(detail['index'], decoder_input_ids)

        interpreter.invoke()

        # Pobranie logitów z wyjścia [1, 256, 32128]
        output_data = interpreter.get_tensor(output_details[0]['index'])

        # Interesuje nas logit dla ostatniego wygenerowanego tokena
        next_token_logits = output_data[0, len(output_tokens) - 1, :]

        # Greedy Search (wybieramy najlepszy token - Argmax)
        next_token = int(np.argmax(next_token_logits))

        # Warunki stopu
        if next_token == 1:  # 1 to EOS (End of String) w T5
            print("LOG: Otrzymano token EOS (1)")
            break

        output_tokens.append(next_token)

        # Dekodowanie na bieżąco
        word = tokenizer.decode([next_token])
        generated_text += word
        print(f"  Step {i}: {next_token} -> '{word}'")

        if len(output_tokens) >= MAX_LEN:
            break

    return generated_text.strip()


def main():
    if not MODEL_PATH.exists():
        print(f"❌ Nie znaleziono pliku modelu w: {MODEL_PATH}")
        return

    print(f"🚀 Ładowanie modelu TFLite: {MODEL_PATH}")
    interpreter = tf.lite.Interpreter(model_path=str(MODEL_PATH))
    interpreter.allocate_tensors()

    print(f"🚀 Ładowanie tokenizera z: {TOKENIZER_DIR}")
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_DIR)

    # Przykładowy test (używamy tekstu, który już znamy)
    sample_text = "Matura 2005 przykład RZECZPOSPOLITA POLSKA ŚWIADECTWO DOJRZAŁOŚCI Janina Kosińska-Iksińska"

    # Test 1: Tytuł
    title = generate_tflite(f"headline: {sample_text}", interpreter, tokenizer)
    print(f"\n📌 FINALNY TYTUŁ TFLITE: {title}")

    # Test 2: Podsumowanie
    summary = generate_tflite(f"summarize: {sample_text}", interpreter, tokenizer)
    print(f"\n📝 FINALNE PODSUMOWANIE TFLITE: {summary}")


if __name__ == "__main__":
    main()