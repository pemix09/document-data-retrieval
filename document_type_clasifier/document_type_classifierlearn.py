import os
import numpy as np
import tensorflow as tf
import json
from pathlib import Path
from collections import Counter
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
from transformers import DistilBertTokenizer, TFDistilBertForSequenceClassification

# --- KONFIGURACJA ŚCIEŻEK ---
# Skrypt jest w podfolderze, więc wychodzimy o jeden poziom wyżej (parent)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = BASE_DIR / "content"
LABEL_ROOT = BASE_DIR / "type"

# Gdzie zapisać wyniki (możesz dostosować)
MODELS_DIR = Path(__file__).resolve().parent
TFLITE_OUTPUT = MODELS_DIR / "document_type_classifier.tflite"
LABELS_OUTPUT = MODELS_DIR / "document_type_labels.txt"

# Parametry modelu
MODEL_ID = "distilbert-base-multilingual-cased"
MIN_SAMPLES_PER_CLASS = 2
MAX_LEN = 256
BATCH_SIZE = 16
EPOCHS = 10  # Zwiększyłem dla lepszej skuteczności


def load_data():
    texts, labels = [], []
    if not DATA_ROOT.exists():
        print(f"❌ BŁĄD: Nie znaleziono folderu content w: {DATA_ROOT}")
        return [], []

    print(f"📂 Wczytywanie danych z: {DATA_ROOT}")
    for text_file in DATA_ROOT.rglob("*.txt"):
        rel_path = text_file.relative_to(DATA_ROOT)
        label_file = LABEL_ROOT / rel_path

        if label_file.exists():
            with open(text_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            with open(label_file, "r", encoding="utf-8") as f:
                label = f.read().strip().lower()

            if content and label:
                texts.append(content)
                labels.append(label)
    return texts, labels


def main():
    # 1. Ładowanie i filtrowanie
    texts, labels = load_data()
    if not texts: return

    counts = Counter(labels)
    valid_classes = [cls for cls, count in counts.items() if count >= MIN_SAMPLES_PER_CLASS]

    filtered_texts, filtered_labels = [], []
    for t, l in zip(texts, labels):
        if l in valid_classes:
            filtered_texts.append(t)
            filtered_labels.append(l)

    print(f"✅ Załadowano {len(filtered_texts)} dokumentów w {len(valid_classes)} kategoriach.")

    # 2. Kodowanie etykiet
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(filtered_labels)
    num_labels = len(label_encoder.classes_)

    with open(LABELS_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(label_encoder.classes_))

    # 3. Podział na zbiory
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        filtered_texts, y, test_size=0.20, random_state=42, stratify=y
    )

    # 4. Tokenizacja
    tokenizer = DistilBertTokenizer.from_pretrained(MODEL_ID)

    def tokenize_data(texts):
        return tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=MAX_LEN,
            return_tensors="tf"
        )

    print("⏳ Tokenizacja danych...")
    train_encodings = dict(tokenize_data(train_texts))
    val_encodings = dict(tokenize_data(val_texts))

    # 5. Budowanie modelu
    print("🏗️  Inicjalizacja DistilBERT...")
    model = TFDistilBertForSequenceClassification.from_pretrained(MODEL_ID, num_labels=num_labels, from_pt=True)

    optimizer = tf.keras.optimizers.legacy.Adam(learning_rate=3e-5)
    loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    model.compile(optimizer=optimizer, loss=loss, metrics=['accuracy'])

    # 6. Trenowanie
    print("\n🚀 Start uczenia...")
    model.fit(
        x=train_encodings,
        y=train_labels,
        validation_data=(val_encodings, val_labels),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE
    )

    # 7. Konwersja do TFLite (FIX: Kompatybilność wsteczna)
    print("\n🔧 Konwersja do TFLite (Generowanie wersji kompatybilnej z Flutterem)...")

    @tf.function(input_signature=[tf.TensorSpec([1, MAX_LEN], tf.int32, name="input_ids")])
    def serving_fn(input_ids):
        # training=False jest kluczowe dla stabilności opów
        return model(input_ids, training=False)

    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [serving_fn.get_concrete_function()], model
    )

    # WYMUSZENIE KOMPATYBILNOŚCI:
    # 1. Standardowe operatory
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS
    ]

    # 2. Wyłączenie optymalizacji, która mogłaby podbić wersję opcode 'FULLY_CONNECTED' do 12
    # Jeśli model będzie za duży, można spróbować przywrócić to po aktualizacji bibliotek we Flutterze
    converter.optimizations = []

    # 3. Wymuszenie formatu wyjściowego
    converter.target_spec.supported_types = [tf.float32]

    tflite_model = converter.convert()
    with open(TFLITE_OUTPUT, "wb") as f:
        f.write(tflite_model)

    print(f"\n✨ SUKCES!")
    print(f"Model: {TFLITE_OUTPUT}")
    print(f"Etykiety: {LABELS_OUTPUT}")


if __name__ == "__main__":
    main()