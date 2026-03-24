#!/usr/bin/env python3
"""Quick benchmark: PaddleOCR-VL-1.5 via PyTorch/transformers on RTX 5090."""
import time
import torch

print(f"PyTorch {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"sm_120 support: {'sm_120' in torch.cuda.get_arch_list()}")

from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image

model_name = "PaddlePaddle/PaddleOCR-VL-1.5"

print("\nLoading processor...")
processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

print("Loading model to GPU (fp16)...")
t0 = time.time()
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    trust_remote_code=True,
    dtype=torch.float16,
    device_map="cuda",
)
t1 = time.time()
print(f"Model loaded in {t1-t0:.1f}s")
print(f"VRAM allocated: {torch.cuda.memory_allocated()/1e9:.2f} GB")

# Test on rendered page image
img = Image.open("/tmp/test_page5.png")
print(f"\nImage size: {img.size}")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": "Parse this document into markdown."},
        ],
    }
]

text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
inputs = processor(text=text, images=[img], return_tensors="pt").to("cuda")

print("Running inference...")
t2 = time.time()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
result = processor.batch_decode(
    out[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
)[0]
t3 = time.time()

print(f"\n{'='*60}")
print(f"Inference time: {t3-t2:.2f}s")
print(f"Output length: {len(result)} chars")
print(f"VRAM peak: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")
print(f"{'='*60}")
print(f"\n--- MARKDOWN OUTPUT ---")
print(result[:2000])
