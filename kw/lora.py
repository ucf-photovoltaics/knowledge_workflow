# -*- coding: utf-8 -*-
"""
LoRA fine-tune — Step 6, the TERMINAL step.

Runs ONLY after the ontology is finished. Builds a supervised dataset from the
run's FINAL ontology terms + mined (text -> value) pairs, then fine-tunes a LoRA
adapter on the base model so future runs extract/ground new material better.
The adapter updates once per finished ontology.

Heavy training is guarded: with `peft`/`transformers`/`torch` (+ ideally a GPU)
it trains and saves an adapter; without them it writes the dataset + manifest so
the pipeline always completes. Run training later by re-calling finetune() in an
environment that has the deps.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

BASE_MODEL  = os.getenv('LORA_BASE_MODEL', 'meta-llama/Llama-3.1-8B')
ADAPTER_DIR = os.getenv('LORA_ADAPTER_DIR', 'lora_adapters')
EPOCHS      = int(os.getenv('LORA_EPOCHS', '3'))
# Opt-in: training is OFF unless LORA_TRAIN=true. A normal run (and any machine
# without a suitable GPU - e.g. Blackwell, which has no bitsandbytes 4-bit yet)
# writes the dataset + manifest only, so the pipeline completes without pulling a
# ~16 GB base model. Train later on a supported GPU by setting LORA_TRAIN=true.
TRAIN       = os.getenv('LORA_TRAIN', 'false').lower() == 'true'


def build_training_examples(concept_list: list[str],
                            schema_path: str | None = None,
                            papers: dict | None = None) -> list[dict]:
    """(instruction, input, output) SFT examples grounded in the final ontology terms."""
    instr = ('Extract the materials-science ontology concepts and their values from the '
             'paper text. Use only these concepts: ' + ', '.join(concept_list) + '.')
    examples: list[dict] = []

    if schema_path and os.path.isfile(schema_path):
        df = pd.read_csv(schema_path, dtype=str).fillna('')
        text_by_doi: dict[str, str] = {}
        if papers:
            for p in papers.values():
                doi = (p.get('doi') or '').strip()
                text_by_doi[doi] = (p.get('full_text') or p.get('abstract') or '')[:6000]
        concept_cols = [c for c in df.columns if c not in ('domain', 'doi')]
        for _, row in df.iterrows():
            doi   = str(row.get('doi', '')).strip()
            text  = text_by_doi.get(doi, '')
            pairs = {c: str(row[c]).split(' | ')[0].strip()
                     for c in concept_cols if str(row.get(c, '')).strip()}
            if not pairs:
                continue
            examples.append({
                'instruction': instr,
                'input':       text or f'(doi: {doi})',
                'output':      json.dumps(pairs, ensure_ascii=False),
            })

    # vocabulary example - teaches the canonical ontology term set itself
    examples.append({
        'instruction': 'List the canonical ontology concepts for this domain.',
        'input':       '',
        'output':      json.dumps(concept_list, ensure_ascii=False),
    })
    return examples


def _write_dataset(examples: list[dict], out: Path) -> str:
    path = out / 'lora_dataset.jsonl'
    with open(path, 'w', encoding='utf-8') as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    return str(path)


def finetune(concept_list: list[str], ttl_path: str,
             schema_path: str | None = None, papers: dict | None = None,
             base_model: str = BASE_MODEL) -> dict:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out   = Path(ADAPTER_DIR) / f'run-{stamp}'
    out.mkdir(parents=True, exist_ok=True)

    examples = build_training_examples(concept_list, schema_path, papers)
    ds_path  = _write_dataset(examples, out)

    manifest = {
        'base_model': base_model, 'ontology': ttl_path,
        'n_terms': len(concept_list), 'n_examples': len(examples),
        'dataset': ds_path, 'created': stamp,
    }
    if not TRAIN:
        manifest['status'] = 'dataset-only (LORA_TRAIN=false)'
        print(f'  [lora] dataset-only (set LORA_TRAIN=true to train); dataset ready at {ds_path}')
    else:
        try:
            adapter = _train_peft(ds_path, base_model, str(out))
            manifest['status']  = 'trained'
            manifest['adapter'] = adapter
            print(f'  [lora] trained adapter -> {adapter}')
        except Exception as exc:
            manifest['status'] = f'dataset-only ({type(exc).__name__})'
            print(f'  [lora] training skipped ({exc}); dataset ready at {ds_path}')

    # T1.5: emit an Ollama Modelfile template so a trained adapter can be
    # registered and reused as the extraction model (close the learning loop).
    modelfile = out / 'Modelfile'
    modelfile.write_text(
        f'# Register this adapter with Ollama, then point extraction at it:\n'
        f'#   ollama create kweave-lora -f "{modelfile}"\n'
        f'#   .env: LLM_MODEL=kweave-lora  LLM_OUTPUT_MODE=native  '
        f'LORA_ADAPTER_PATH={out}\n'
        f'FROM {base_model}\n'
        f'ADAPTER .\n',
        encoding='utf-8')
    manifest['modelfile'] = str(modelfile)

    with open(out / 'lora_manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    return {'adapter_dir': str(out), 'dataset': ds_path, 'modelfile': str(modelfile),
            'adapter_version': f'lora-{stamp}', 'status': manifest['status']}


def _train_peft(jsonl_path: str, base_model: str, adapter_dir: str) -> str:
    """Real LoRA SFT. Raises if deps/GPU are unavailable (caught by finetune)."""
    import torch
    from datasets import load_dataset
    from transformers import (AutoTokenizer, AutoModelForCausalLM,
                              TrainingArguments, Trainer, DataCollatorForLanguageModeling)
    from peft import LoraConfig, get_peft_model

    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias='none',
        task_type='CAUSAL_LM', target_modules=['q_proj', 'v_proj'],
    ))

    ds = load_dataset('json', data_files=jsonl_path, split='train')

    def _fmt(ex):
        prompt = (f"### Instruction:\n{ex['instruction']}\n\n"
                  f"### Input:\n{ex['input']}\n\n"
                  f"### Response:\n{ex['output']}{tok.eos_token}")
        return tok(prompt, truncation=True, max_length=1024, padding='max_length')

    ds = ds.map(_fmt, remove_columns=ds.column_names)
    Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=adapter_dir, per_device_train_batch_size=1,
            gradient_accumulation_steps=8, num_train_epochs=EPOCHS,
            learning_rate=2e-4, logging_steps=5, save_strategy='no',
            fp16=torch.cuda.is_available(), report_to=[],
        ),
        train_dataset=ds,
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    ).train()

    model.save_pretrained(adapter_dir)
    tok.save_pretrained(adapter_dir)
    return adapter_dir
