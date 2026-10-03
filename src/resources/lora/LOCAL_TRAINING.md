# Train the LoRA adapter on your own GPU (WSL2)

For GPUs with native bf16 (RTX 30xx or newer, e.g. the 5070 Ti). Does the same training as `finetune_colab.ipynb`, reading `outputs/lora/data/` directly (no zip, no uploads).

## One-time setup

1. In PowerShell (admin), if WSL isn't installed yet: `wsl --install -d Ubuntu`, then restart.
   The normal Windows NVIDIA driver also serves WSL; don't install a driver inside Ubuntu.
2. In Ubuntu:
   ```bash
   nvidia-smi                      # must list the GPU
   sudo apt update && sudo apt install -y build-essential cmake git curl libcurl4-openssl-dev
   curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
   uv venv ~/kw-train --python 3.12
   source ~/kw-train/bin/activate
   uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # CUDA 12.8: needed for RTX 50xx
   uv pip install unsloth
   python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
   The environment lives in the Ubuntu home (`~/kw-train`), which is much faster than `/mnt/c`.
   `build-essential`, `cmake` and `libcurl` are for the GGUF export (Unsloth builds llama.cpp the first time).

## Each training round

1. Windows, from `opus_knowledge_workflow`: `uv run --with-requirements requirements.txt python -m src.run lora-data`
2. Quit Ollama (tray icon → Quit) so the GPU memory is free.
3. Ubuntu:
   ```bash
   source ~/kw-train/bin/activate
   cd /mnt/c/Users/brent/dev/opus_knowledge_workflow
   python src/resources/lora/train_local.py               # 2B; or: --size 4B --max-seq 3072
   ```
   If it stops partway, rerun with `--resume`. Out of memory: lower `--max-seq` (e.g. 3072).
4. Output in `outputs/lora/`: `kw-qwen3.5-2b-lora.Q4_K_M.gguf`, the adapter folder and `kw-qwen3.5-2b-lora-training.json`.
5. Windows, start Ollama again, then:
   ```
   ollama create kw-qwen3.5-2b-lora-32k -f src/resources/ollama/Modelfile.lora
   uv run --with-requirements requirements.txt python -m src.run lora-eval --model kw-qwen3.5-2b-32k
   uv run --with-requirements requirements.txt python -m src.run lora-eval --model kw-qwen3.5-2b-lora-32k
   ```
   `Modelfile.lora` and the `ollama-lora` profile are set up for the 9B (A100 via Colab). For a local 2B or 4B run, change `9b` to `2b`/`4b` there and in these commands (baseline `qwen3.5:2b`/`qwen3.5:4b`).
