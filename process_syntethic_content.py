import os
import json
from pathlib import Path
from langchain_ollama import OllamaLLM

# --- KONFIGURACJA ---
INPUT_DIR = "synthetic_content"       
OUTPUT_ROOT = "synthetic_dataset"     
HISTORY_FILE = "processed_synthetic_scans_contents.txt" 
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

# Inicjalizacja LLM z niską temperaturą dla powtarzalności
llm = OllamaLLM(model=MODEL_NAME, temperature=0)

# --- OBSŁUGA HISTORII (RESUME) ---
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_done(rel_path):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{rel_path}\n")

# --- PROMPTY LLM ---
def ask_llm_json(prompt):
    """Wywołuje LLM w trybie JSON i bezpiecznie parsuje wynik."""
    try:
        # format="json" to kluczowa funkcja Ollama, która wymusza poprawny JSON
        response = llm.invoke(prompt, format="json")
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"\n   ⚠️ Błąd składni JSON od AI: {e}")
        return None
    except Exception as e:
        print(f"\n   ⚠️ Błąd komunikacji z LLM: {e}")
        return None

def ask_llm_text(prompt):
    try:
        response = llm.invoke(prompt)
        return response.strip().strip('"').strip("'")
    except Exception:
        return "Translation Error"

def get_metadata(text, hinted_type):
    # Prompt z wyraźnymi instrukcjami dla formatu JSON
    prompt = f"""
    Analyze this document text.
    Folder hint: {hinted_type}

    Return ONLY a JSON object with these keys:
    - "title_base": Factual title in ENGLISH (format: "[Type] - [Entity] - [Date]")
    - "summary_base": Factual summary in ENGLISH (exactly 5 sentences)
    - "category": One of: financial, legal, personal, health, property, other
    - "info": Key details (e.g. document ID or service name)

    Ensure all quotes inside the text are properly escaped.
    
    TEXT:
    {text[:3500]}
    """
    return ask_llm_json(prompt)

def translate_section(text, target_lang, content_type="text"):
    prompt = f"""
    Translate the following {content_type} into {target_lang}.
    Output ONLY the translation. No conversational text or markdown.
    
    TEXT TO TRANSLATE:
    {text}
    """
    return ask_llm_text(prompt)

def save_output(root, kind, lang, subdir, filename, content):
    if lang:
        path = Path(root) / kind / lang / subdir
    else:
        path = Path(root) / kind / subdir
        
    path.mkdir(parents=True, exist_ok=True)
    with open(path / filename, "w", encoding="utf-8") as f:
        f.write(str(content))

# --- GŁÓWNA LOGIKA PLIKU ---
def process_file(file_path, input_root):
    rel_path = file_path.relative_to(input_root)
    base_filename = rel_path.name
    sub_dir = rel_path.parent
    doc_type = sub_dir.name

    try:
        raw_text = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"   ❌ Błąd odczytu pliku: {e}")
        return

    # 2. Generowanie metadanych (JSON)
    meta = get_metadata(raw_text, doc_type)
    if not meta or not isinstance(meta, dict):
        print("   ❌ Błąd AI: Nie udało się wygenerować poprawnego JSONa.")
        return

    # 3. Zapisywanie danych podstawowych
    save_output(OUTPUT_ROOT, "content", None, sub_dir, base_filename, raw_text)
    save_output(OUTPUT_ROOT, "category", None, sub_dir, base_filename, meta.get("category", "other"))
    save_output(OUTPUT_ROOT, "type", None, sub_dir, base_filename, doc_type)
    save_output(OUTPUT_ROOT, "info", None, sub_dir, base_filename, meta.get("info", "none"))

    base_title = meta.get("title_base", "Document")
    base_summary = meta.get("summary_base", "No summary available.")

    # 4. Tłumaczenia
    print(f"   🌍 Tłumaczenie na {len(TARGET_LANGUAGES)} języków...", end="", flush=True)
    
    for code, lang_name in TARGET_LANGUAGES.items():
        # Tytuły
        if code == "en": 
            title = base_title
        else: 
            title = translate_section(base_title, lang_name, "title")
        save_output(OUTPUT_ROOT, "titles", code, sub_dir, base_filename, title)

        # Streszczenia
        if code == "en": 
            summary = base_summary
        else: 
            summary = translate_section(base_summary, lang_name, "summary")
        save_output(OUTPUT_ROOT, "summary", code, sub_dir, base_filename, summary)

        print(".", end="", flush=True)

    print(" OK")
    mark_as_done(str(rel_path))

def main():
    input_path = Path(INPUT_DIR)
    if not input_path.exists():
        print(f"❌ Brak folderu wejściowego: {INPUT_DIR}")
        return

    processed = load_history()
    print(f"📂 Historia: {len(processed)} plików już przetworzonych.")

    files = list(input_path.rglob("*.txt"))
    print(f"🚀 Start: {len(files)} plików do analizy.")

    for f in files:
        rel_path = str(f.relative_to(input_path))
        
        if rel_path in processed:
            continue
            
        print(f"📄 Przetwarzam: {rel_path}")
        try:
            process_file(f, input_path)
        except KeyboardInterrupt:
            print("\n🛑 Przerwano ręcznie. Postęp zapisany.")
            break
        except Exception as e:
            print(f"\n❌ Błąd krytyczny przy pliku {rel_path}: {e}")

if __name__ == "__main__":
    main()