---
type: project
level: strong
last-used: 2026-05
evidence: thesis submitted (IAS, Uni Stuttgart)
cv-ready: true
---
# Master Thesis — Risk-Aware Autonomy (Edge FMECA)
Multithreaded edge-AI pipeline on Jetson AGX Orin: RGB-D via [[ROS2]] → YOLO-E + BoT-SORT → LLM-generated FMECA. Dual-store RAG (Neo4j + ChromaDB), faithfulness 0.66→0.80. Benchmarked 7 LLM configs on 3 backends ([[TensorRT]]-LLM, vLLM, llama.cpp); byte-identical deterministic inference; memory-bandwidth bottleneck profiling.
NOT evidenced: hand-written CUDA kernels.
Links: [[Edge AI]], [[Jetson]], [[C++]]

## Requirements engineering (user-stated 2026-07-14, cv-ready)
Thesis began from the supervisor's user requirement document; Shashank derived the system requirements from it and carried them through design, implementation, and validation of the working perception system, checking at each step what was actually needed rather than what was written. CV-eligible bullet candidate: "Derived system requirements from a user requirement document and carried them through design, implementation, and validation".

Grade (2026-08-05): thesis result received; M.Sc. overall grade is now 1.8 on the German scale, up from 2.0. The individual thesis grade was not reported and is not shown on the CV.

## Quantization evidence (thesis-verified 2026-08-25, cv-ready)
Verified directly from the thesis sources at /home/shashaank/M.Sc/Thesis (build pipeline doc EFORIA/eforia/GET_SPECULATIONS/tensorrt-llm-build-pipeline.md and Evaluation-and-Results.tex), prompted by the Sarvam card question and his answer "AWQ".
- Ran the TensorRT-LLM quantization step himself on the Jetson AGX Orin 64GB: quantize.py with qformat int4_awq, awq_block_size 128, producing an INT4 AWQ checkpoint for Qwen2.5-3B-Instruct, then compiled it with trtllm-build into a TensorRT engine (TRT-LLM 0.12). W4A16, weights INT4, FP16 compute and accumulation.
- Model selection driven by a measured latency budget: 8B at INT4 AWQ gave ~18 tok/s on Orin, too slow for the 15s budget, so 3B was chosen.
- Served three INT4 AWQ Qwen2.5 configs via TRT-LLM plus Qwen3-4B-Thinking INT4 AWQ via vLLM, NF4 BitsAndBytes (SmolLM3-3B), and Q4_K_M GGUF via llama.cpp; the quantisation schemes and their memory-access trade-offs are analysed in the thesis text.
- Accuracy and validity checks in the deployed pipeline: reproducibility verified to byte-identical output (see the 2026-09-20 correction below on WHY it was deterministic), Krippendorff Alpha 1.0 on the three ordinal FMECA fields for the deterministic configs; memory-bandwidth ceiling profiled (168.9 GB/s sustained vs 204.8 peak, ~112 tok/s bound for 3B INT4).
- NOT evidenced: a formal quantised-vs-FP16 accuracy-degradation study with a calibration dataset he curated; the AWQ calibration used the quantize.py defaults. Do not claim a custom calibration set.
- ONNX export: no ONNX work anywhere in the thesis tree (checked 2026-08-25); if ONNX evidence exists it must come from elsewhere.

## Scene graph terminology (thesis-verified 2026-09-11, cv-ready)
Verified from the thesis sources at /home/shashaank/M.Sc/Thesis after a nightly critic challenged the term as unevidenced. The pipeline carries a dedicated `scene_graph.py` module under EFORIA/eforia/GET_SPECULATIONS/src/eforia_speculate/, and the term appears 69 times across the sources including the prompt templates in the writing appendix. "Structured scene graphs" on the CV is backed by the primary source. The challenge was a gap in this note rather than a gap in the work, and the note is now corrected.

## Bandwidth ceiling applies to the LANGUAGE stage (thesis-verified 2026-09-11)
The 168.9 GB/s sustained against 204.8 GB/s peak figure in `writing/IAS-NAS Latex Template/Sections/Evaluation-and-Results.tex:186` bounds LLM token decode, not perception. `Appendices/parallel_consumer.tex` shows YOLO detection competing for the bus, but every degraded figure quoted there is an LLM stage. Never write that the detection and tracking stage was bandwidth-bound.

## Determinism was DIAGNOSED, not configured (thesis-verified 2026-09-20, nightly run)
A nightly evidence critic checked the "fixed sampler seed" wording above against the primary source and it is WRONG at source. `writing/IAS-NAS Latex Template/Sections/Evaluation-and-Results.tex:353` states that the pipeline does NOT pass an explicit random seed in the API request, and `:395` that TensorRT-LLM defaults its sampler seed to zero when none is given. The reduction order is frozen by TensorRT when the engine is built, not set by him.
- NEVER claim he pinned the seed or the reduction order. He did neither.
- The claimable statement is that he MEASURED byte-identical output under the compiled TensorRT-LLM engines and traced the cause, the library's default zero seed, near-one-hot sampling at temperature 0.3, and the GEMM reduction order frozen into the compiled engine. Diagnosing why a system is deterministic is the stronger claim anyway.
- The CV bullet "Documented the byte-identical output only under the compiled TensorRT-LLM engines" was already correct and needed no change.

## 8B throughput is a PLANNING ESTIMATE, not a measurement (thesis-verified 2026-09-20, nightly run)
The ~18 tok/s figure for the 8B model appears once, in a change-log table cell in `EFORIA/eforia/GET_SPECULATIONS/tensorrt-llm-build-pipeline.md:10`, reading "8B INT4 AWQ yields ~18 tok/s on Orin - too slow for 15s budget; 3B estimated 60-100 tok/s". There is no 8B row in the measured throughput table, no 8B benchmark script and no 8B result file in the tree. The same cell's 3B estimate of 60-100 tok/s is contradicted by the later MEASURED 36-40 tok/s, which shows the line is a pre-build estimate.
- Write it as a projection that drove model selection, never as a measured result.

## Quantisation scope, what he personally ran (thesis-verified 2026-09-20, nightly run)
He ran `quantize.py --qformat int4_awq --awq_block_size 128` and `trtllm-build` ONLY for the Qwen2.5 checkpoints served through TensorRT-LLM. Of the seven benchmarked configurations, SmolLM3-3B is NF4 bitsandbytes applied at load by vLLM and the GGUF config is a downloaded Q4_K_M under llama.cpp, neither of which he quantised or compiled. Scope any quantisation sentence to the TensorRT-LLM builds.
