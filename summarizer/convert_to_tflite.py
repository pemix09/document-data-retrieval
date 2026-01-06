import os
import tensorflow as tf
from transformers import TFT5ForConditionalGeneration, AutoTokenizer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_INPUT_DIR = BASE_DIR / "summarizer" / "models" / "flan_t5_custom"
TFLITE_OUTPUT_FILE = BASE_DIR / "summarizer" / "models" / "summarizer.tflite"

# USTAWAMY IDENTYCZNE WARTOŚCI - to rozwiązuje błąd "not broadcastable"
MAX_LEN = 256


def convert():
    print(f"🚀 Konwersja z wyrównaniem kształtów do {MAX_LEN}...")

    model = TFT5ForConditionalGeneration.from_pretrained(MODEL_INPUT_DIR, from_pt=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_INPUT_DIR)

    class T5MergedModel(tf.Module):
        def __init__(self, model):
            super(T5MergedModel, self).__init__()
            self.model = model

        @tf.function(input_signature=[
            tf.TensorSpec([1, MAX_LEN], tf.int32, name="input_ids"),
            tf.TensorSpec([1, MAX_LEN], tf.int32, name="decoder_input_ids")
        ])
        def __call__(self, input_ids, decoder_input_ids):
            # training=False jest kluczowe dla usunięcia węzłów treningowych
            output = self.model(input_ids=input_ids, decoder_input_ids=decoder_input_ids, training=False)
            return output.logits

    t5_module = T5MergedModel(model)
    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [t5_module.__call__.get_concrete_function()], t5_module
    )

    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS
    ]

    # Optymalizacja pod kątem rozmiaru i stabilności
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float32]

    tflite_model = converter.convert()
    with open(TFLITE_OUTPUT_FILE, "wb") as f:
        f.write(tflite_model)

    print(f"✨ Model gotowy: {TFLITE_OUTPUT_FILE}")


if __name__ == "__main__":
    convert()