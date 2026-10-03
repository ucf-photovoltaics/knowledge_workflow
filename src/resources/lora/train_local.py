"""Train the LoRA adapter on your own GPU (e.g. RTX 5070 Ti, 12 GB) with Unsloth, in WSL2 or Linux.

Same training as finetune_colab.ipynb, reading outputs/lora/data/ (built by `python -m src.run lora-data`) and writing
the adapter, a 4-bit GGUF and a training log to outputs/lora/. Setup and usage: src/resources/lora/LOCAL_TRAINING.md

  python src/resources/lora/train_local.py                 # 2B (default)
  python src/resources/lora/train_local.py --size 4B --max-seq 3072
"""
import argparse
import glob
import json
import math
import os
import shutil
from collections import Counter
from pathlib import Path

os.environ["UNSLOTH_SKIP_TORCHVISION_CHECK"] = "1"  # text-only training never uses torchvision

ROOT = Path(__file__).resolve().parents[3]
DATA, OUT = ROOT / "outputs" / "lora" / "data", ROOT / "outputs" / "lora"
ap = argparse.ArgumentParser(description="LoRA fine-tune of Qwen 3.5 on the pipeline's training data")
ap.add_argument("--size", default="2B", choices=["2B", "4B"], help="4B needs --max-seq 3072 or less on 12 GB")
ap.add_argument("--max-seq", type=int, default=4096, help="longer examples are dropped (the count is printed)")
ap.add_argument("--epochs", type=int, default=2)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--rank", type=int, default=16)
ap.add_argument("--grad-accum", type=int, default=8)
ap.add_argument("--no-gguf", action="store_true", help="save only the adapter")
ap.add_argument("--resume", action="store_true", help="continue an interrupted run from its last checkpoint")
args = ap.parse_args()

import torch  # noqa: E402  (after the env var above)
assert torch.cuda.is_available(), "No CUDA GPU visible. In WSL2, check `nvidia-smi` works first."
assert torch.cuda.get_device_capability(0)[0] >= 8, "This script needs native bf16 (RTX 30xx or newer)."
print(torch.cuda.get_device_name(0), f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.0f} GB")

from unsloth import FastLanguageModel  # noqa: E402
from unsloth.chat_templates import train_on_responses_only  # noqa: E402
from datasets import load_dataset  # noqa: E402
from trl import SFTConfig, SFTTrainer  # noqa: E402

MODEL_NAME = f"Qwen/Qwen3.5-{args.size}"
RUN_NAME = f"kw-qwen3.5-{args.size.lower()}-lora"
model, tokenizer = FastLanguageModel.from_pretrained(model_name=MODEL_NAME, max_seq_length=args.max_seq,
                                                     load_in_4bit=False, load_in_16bit=True, full_finetuning=False)
tok = getattr(tokenizer, "tokenizer", tokenizer)


def to_text(example):
    try:
        text = tokenizer.apply_chat_template(example["messages"], tokenize=False, enable_thinking=False)
    except TypeError:
        text = tokenizer.apply_chat_template(example["messages"], tokenize=False)
    return {"text": text, "n_tokens": len(tok(text).input_ids)}


data = load_dataset("json", data_files={s: str(DATA / f"{s}.jsonl") for s in ("train", "val")}).map(to_text)
for split in ("train", "val"):
    before = len(data[split])
    data[split] = data[split].filter(lambda e: e["n_tokens"] <= args.max_seq)
    print(f"{split}: kept {len(data[split])}/{before} examples (<= {args.max_seq} tokens)")
print("train tasks:", dict(Counter(data["train"]["task"])))

model = FastLanguageModel.get_peft_model(
    model, r=args.rank, lora_alpha=args.rank, lora_dropout=0, bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth", random_state=3407, max_seq_length=args.max_seq)

ckpt_dir = OUT / f"{RUN_NAME}-checkpoints"
trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=data["train"], eval_dataset=data["val"],
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=args.max_seq,
        per_device_train_batch_size=1, gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_steps=max(1, math.ceil(0.03 * args.epochs * len(data["train"]) / args.grad_accum)),
        logging_steps=5, eval_strategy="steps", eval_steps=50, save_strategy="steps", save_steps=100,
        optim="adamw_8bit", weight_decay=0.01, bf16=True, fp16=False, seed=3407,
        output_dir=str(ckpt_dir), report_to="none", dataset_num_proc=1))
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n", response_part="<|im_start|>assistant\n")
resume = args.resume and bool(glob.glob(str(ckpt_dir / "checkpoint-*")))
stats = trainer.train(resume_from_checkpoint=True if resume else None)

adapter = OUT / f"{RUN_NAME}-adapter"
model.save_pretrained(str(adapter))
tokenizer.save_pretrained(str(adapter))
(OUT / f"{RUN_NAME}-training.json").write_text(json.dumps(
    {"base": MODEL_NAME, "r": args.rank, "alpha": args.rank, "epochs": args.epochs, "lr": args.lr,
     "max_seq": args.max_seq, "train_examples": len(data["train"]), "val_examples": len(data["val"]),
     "train_loss": stats.training_loss, "log_history": trainer.state.log_history}, indent=1), encoding="utf-8")
print("adapter saved to", adapter)

if not args.no_gguf:
    gguf_dir = OUT / f"{RUN_NAME}-gguf"
    model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method="q4_k_m")
    found = [f for f in glob.glob(f"{gguf_dir}*/**/*.gguf", recursive=True) if "q4_k_m" in f.lower()]
    shutil.copy(found[0], OUT / f"{RUN_NAME}.Q4_K_M.gguf")
    print("GGUF saved to", OUT / f"{RUN_NAME}.Q4_K_M.gguf")
