---
type: skill
level: strong
last-used: 2026-05
evidence: TensorRT-LLM 0.12 quantisation and engine builds in the Master Thesis
cv-ready: true
---
# TensorRT
TensorRT-LLM 0.12 on [[Jetson]]. He ran `quantize.py` with `qformat int4_awq` and `awq_block_size 128` on Qwen2.5 checkpoints, then compiled them with `trtllm-build`. W4A16, weights at INT4 with FP16 compute.

Scope. The quantisation claim covers the TensorRT-LLM builds only. The NF4 bitsandbytes and GGUF configurations in the same benchmark were applied by vLLM at load and downloaded respectively, and he quantised neither.

NOT evidenced: a custom calibration dataset, since the AWQ calibration used the defaults. No ONNX work exists anywhere in the thesis tree.
