import os, sys, torch
from transformers import AutoModelForCausalLM, AutoTokenizer, logging

logging.set_verbosity_error()  # suppress repetitive warnings

model_name = os.getenv("MODEL", "gpt2")
device = "cuda" if torch.cuda.is_available() else "cpu"

# Offline hint: set TRANSFORMERS_OFFLINE=1 after first download if no network.
tokenizer = AutoTokenizer.from_pretrained(model_name)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token  # define pad to silence pad warnings

model = AutoModelForCausalLM.from_pretrained(model_name).to(device)

I = int(os.getenv("ITERS", "50"))
prompt = "Hello world"
enc = tokenizer(prompt, return_tensors="pt")
ids = enc.input_ids.to(device)
attn = enc.get("attention_mask", torch.ones_like(ids)).to(device)

# Warmup (optional) to reduce first-iter overhead
_ = model.generate(ids, attention_mask=attn, max_new_tokens=4, do_sample=False)
if device == "cuda":
    torch.cuda.synchronize()

for i in range(I):
    out = model.generate(
        ids,
        attention_mask=attn,
        max_new_tokens=32,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id
    )
    if device == "cuda":
        torch.cuda.synchronize()
    if (i + 1) % 10 == 0:
        print(f"iter {i+1}/{I} length={out.shape[-1]}")
print("Transformer inference done")