import os
import torch
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM, 
    DataCollatorForSeq2Seq, 
    Seq2SeqTrainingArguments, 
    Seq2SeqTrainer
)

# --- KONFIGURACJA ŚCIEŻEK ---
# Wyjście o jeden poziom wyżej z folderu 'summarizer' do głównego folderu projektu
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = BASE_DIR / "content"
TITLE_ROOT = BASE_DIR / "titles"
SUMMARY_ROOT = BASE_DIR / "summary"

MODEL_ID = "google/flan-t5-small"
OUTPUT_MODEL_DIR = BASE_DIR / "summarizer" / "models" / "flan_t5_custom"

MAX_INPUT_LEN = 512
MAX_TARGET_LEN = 128

def load_data():
    """Wczytuje dane i tworzy pary: Instrukcja + Tekst -> Wynik."""
    dataset_dict = {"input_text": [], "target_text": []}
    
    print(f"📂 Szukam danych w: {DATA_ROOT}")
    
    # Przeszukujemy foldery rekurencyjnie
    files = list(DATA_ROOT.rglob("*.txt"))
    for txt_file in files:
        rel_path = txt_file.relative_to(DATA_ROOT)
        
        # 1. Wczytaj surowy tekst (cecha wejściowa)
        with open(txt_file, "r", encoding="utf-8") as f:
            ocr_content = f.read().strip()
        
        if not ocr_content: continue

        # 2. Dodaj parę dla zadania HEADLINE
        t_file = TITLE_ROOT / rel_path
        if t_file.exists():
            with open(t_file, "r", encoding="utf-8") as f:
                dataset_dict["input_text"].append(f"headline: {ocr_content}")
                dataset_dict["target_text"].append(f.read().strip())
        
        # 3. Dodaj parę dla zadania SUMMARIZE
        s_file = SUMMARY_ROOT / rel_path
        if s_file.exists():
            with open(s_file, "r", encoding="utf-8") as f:
                dataset_dict["input_text"].append(f"summarize: {ocr_content}")
                dataset_dict["target_text"].append(f.read().strip())
                
    return Dataset.from_dict(dataset_dict)

def main():
    # 1. Przygotowanie danych
    raw_dataset = load_data()
    if len(raw_dataset) == 0:
        print("❌ Nie znaleziono plików w content/titles/summary. Sprawdź ścieżki.")
        return
        
    dataset = raw_dataset.train_test_split(test_size=0.1)
    
    # 2. Tokenizer i Model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)

    def preprocess(examples):
        inputs = [ex for ex in examples["input_text"]]
        model_inputs = tokenizer(inputs, max_length=MAX_INPUT_LEN, truncation=True, padding="max_length")
        
        labels = tokenizer(text_target=examples["target_text"], max_length=MAX_TARGET_LEN, truncation=True, padding="max_length")
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    tokenized_dataset = dataset.map(preprocess, batched=True)

    # 3. Argumenty treningu
    # 3. Argumenty treningu
    training_args = Seq2SeqTrainingArguments(
        output_dir="./tmp_results",
        eval_strategy="epoch",  # <--- Zmieniono z evaluation_strategy
        learning_rate=3e-4,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        weight_decay=0.01,
        save_total_limit=2,
        num_train_epochs=15,
        predict_with_generate=True,
        fp16=False,
        logging_steps=10,
        # Opcjonalnie dodaj te parametry dla lepszego generowania:
        generation_max_length=MAX_TARGET_LEN,
        generation_num_beams=4,
    )

    # 4. Trener
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["test"],
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )

    print(f"🚀 Rozpoczynam uczenie na {len(raw_dataset)} przykładach...")
    trainer.train()

    # 5. Zapisywanie modelu
    os.makedirs(OUTPUT_MODEL_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print(f"✨ Model wyuczony i zapisany w: {OUTPUT_MODEL_DIR}")

if __name__ == "__main__":
    main()