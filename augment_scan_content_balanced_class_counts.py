import os
import random
from pathlib import Path
from langchain_ollama import OllamaLLM

# --- KONFIGURACJA ---
INPUT_DIR = "content"
OUTPUT_DIR = "synthetic_content"
LOG_FILE = "synthetic_processed_files.log"  # Plik z historią przetworzonych dokumentów
MODEL_NAME = "llama3"

TARGET_COUNT_PER_TYPE = 60
MIN_SYNTHETIC_PER_FILE = 1

# Ustawienia AI - obniżona temperatura dla stabilności formatu, 
# ale wciąż wystarczająca dla różnorodności
llm = OllamaLLM(model=MODEL_NAME, temperature=0.7)

def load_processed_files():
    """Wczytuje listę już przetworzonych plików."""
    if not Path(LOG_FILE).exists():
        return set()
    return set(Path(LOG_FILE).read_text(encoding='utf-8').splitlines())

def save_to_log(file_path):
    """Zapisuje ścieżkę pliku do logu."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{file_path}\n")

def get_files_by_category(input_path):
    categories = {}
    for item in input_path.iterdir():
        if item.is_dir():
            files = list(item.glob("*.txt"))
            if files:
                categories[item.name] = files
    return categories

def calculate_variants_map(files, target_total):
    current_count = len(files)
    assignments = {f: MIN_SYNTHETIC_PER_FILE for f in files}
    current_total_projected = current_count + (current_count * MIN_SYNTHETIC_PER_FILE)
    missing = target_total - current_total_projected

    if missing <= 0:
        return assignments

    base_add = missing // current_count
    remainder = missing % current_count
    for f in files:
        assignments[f] += base_add
    for f in random.sample(files, remainder):
        assignments[f] += 1
    return assignments

def generate_synthetic_text(text):
    """Generuje tekst, wymuszając brak komentarzy od AI."""
    prompt = f"""[SYSTEM: You are a raw data generator. Return ONLY the document text. No conversational fillers.]
SOURCE DOCUMENT TO TRANSFORM:
{text[:3500]}

TASK:
1. Create a synthetic version of this document.
2. Fill all placeholders/blanks with realistic Polish data.
3. Replace all existing names, dates, and numbers with new ones.
4. Add minor OCR errors (swapped letters, missing spaces).
5. Output MUST be in Polish.

OUTPUT ONLY THE TRANSFORMED TEXT. DO NOT EXPLAIN. DO NOT SAY "HERE IS THE TEXT".
---
SYNTHETIC TEXT START:"""

    try:
        response = llm.invoke(prompt)
        # Czyszczenie techniczne
        clean_text = response.replace("SYNTHETIC TEXT START:", "").strip()
        # Usuwanie ewentualnych bloków kodu markdown
        clean_text = clean_text.replace("```text", "").replace("```", "").strip()
        return clean_text
    except Exception as e:
        print(f"      ❌ Błąd AI: {e}")
        return None

def main():
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)
    processed_files = load_processed_files()

    if not input_path.exists():
        print(f"❌ Brak folderu {INPUT_DIR}")
        return

    print("🔍 Analiza struktury i historii...")
    categories = get_files_by_category(input_path)
    if not categories:
        return

    max_files = max(len(files) for files in categories.values())
    final_target = TARGET_COUNT_PER_TYPE if TARGET_COUNT_PER_TYPE > 0 else max_files
    if final_target < max_files:
        final_target = max_files + (max_files * MIN_SYNTHETIC_PER_FILE)

    total_generated = 0

    for cat_name, files in categories.items():
        target_dir = output_path / cat_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Filtrowanie plików, które już były przetwarzane
        files_to_process = [f for f in files if str(f) not in processed_files]
        
        if not files_to_process:
            print(f"✅ Kategoria [{cat_name}] już w pełni przetworzona.")
            continue

        augment_plan = calculate_variants_map(files_to_process, final_target)
        print(f"\n📂 Kategoria: [{cat_name}] (Przetwarzanie {len(files_to_process)} nowych plików)")

        for file_path in files_to_process:
            try:
                original_text = file_path.read_text(encoding='utf-8')
            except:
                continue

            # Kopiuj oryginał do folderu wyjściowego
            (target_dir / file_path.name).write_text(original_text, encoding='utf-8')

            num_variants = augment_plan[file_path]
            print(f"   📄 {file_path.name} ({num_variants} wariantów)", end=" ", flush=True)

            for i in range(1, num_variants + 1):
                new_text = generate_synthetic_text(original_text)
                if new_text:
                    new_name = f"{file_path.stem}_synth_{i}.txt"
                    (target_dir / new_name).write_text(new_text, encoding='utf-8')
                    total_generated += 1
                    print(".", end="", flush=True)
            
            # Po udanym przetworzeniu wszystkich wariantów dla pliku, zapisz go do logu
            save_to_log(str(file_path))
            print(" Gotowe")

    print(f"\n✅ Zakończono! Wygenerowano {total_generated} nowych plików.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Zatrzymano ręcznie.")