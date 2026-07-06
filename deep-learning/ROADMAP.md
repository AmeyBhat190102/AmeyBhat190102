# The Complete Deep Learning Roadmap (2026 Edition)

> A stage-by-stage path from fundamentals to the research frontier, current as of mid-2026.
> Each stage lists **what to learn**, **why it matters**, **the best resources**, and a **milestone project** that proves you actually learned it. Do not skip milestones — reading is not learning.

---

## How to use this roadmap

- **Time budget:** ~12–18 months at 10–15 hrs/week to reach Stage 8. Stages 9–11 are ongoing.
- **The 70/30 rule:** 70% of your time building/coding, 30% reading/watching. If the ratio flips, you're procrastinating with content.
- **One notebook per concept:** re-implement everything minimally from scratch at least once before using a library abstraction.
- **Track your work publicly:** push every milestone project to GitHub. Your portfolio *is* your credential in this field.

```
Stage 0  Math & Programming Foundations
Stage 1  Machine Learning Core
Stage 2  Neural Networks from Scratch
Stage 3  Deep Learning Frameworks & Training Craft
Stage 4  Core Architectures (CNNs, RNNs, Attention)
Stage 5  Transformers & Large Language Models
Stage 6  Generative Models (Diffusion, Flow Matching, VAEs, GANs)
Stage 7  Specialized Domains (Graphs, RL, Audio, Video, Science)
Stage 8  Scaling, Efficiency & Systems (MLOps for DL)
Stage 9  The 2025–2026 Frontier (Reasoning, SSMs, World Models, Agents)
Stage 10 Trust: Interpretability, Robustness, Alignment, Uncertainty
Stage 11 Research Skills & Staying Current
```

---

## Stage 0 — Math & Programming Foundations (4–6 weeks)

You need *working fluency*, not a math degree. Learn the math lazily-but-honestly: enough to derive backprop by hand and read a paper's methods section without panic.

### Learn
- **Linear algebra:** vectors, matrices, matrix multiplication as transformation, eigenvalues/eigenvectors, SVD, norms, projections. *This is the language of deep learning.*
- **Calculus:** partial derivatives, gradients, the chain rule (this is 90% of backprop), Jacobians, Taylor approximation.
- **Probability & statistics:** random variables, distributions (Gaussian, Bernoulli, categorical), Bayes' rule, expectation/variance, maximum likelihood estimation, KL divergence, entropy.
- **Optimization basics:** convexity (and why DL is non-convex), gradient descent, learning rates, saddle points, local minima.
- **Python engineering:** NumPy (broadcasting is essential), pandas, matplotlib, virtual environments, git, debugging with a real debugger, writing tests.

### Resources
- 3Blue1Brown — *Essence of Linear Algebra* and *Essence of Calculus* (YouTube)
- *Mathematics for Machine Learning* — Deisenroth, Faisal, Ong (free PDF)
- Gilbert Strang's MIT 18.06 Linear Algebra lectures
- *Python for Data Analysis* — Wes McKinney

### Milestone
Implement linear regression **and** logistic regression from scratch in NumPy: loss functions, gradients derived by hand, gradient descent loop, plots of the loss curve. No sklearn.

---

## Stage 1 — Machine Learning Core (4–6 weeks)

Deep learning is a subset of ML. Skipping classical ML produces practitioners who can't diagnose why their model fails.

### Learn
- Supervised vs. unsupervised vs. self-supervised vs. reinforcement learning
- **The bias–variance tradeoff, overfitting, underfitting** — the single most important mental model in ML
- Train/validation/test splits, cross-validation, **data leakage** (the #1 silent killer of real projects)
- Regularization: L1/L2, early stopping
- Classical models (know them, understand when they *beat* deep learning): linear/logistic regression, decision trees, random forests, **gradient boosting (XGBoost/LightGBM — still SOTA on most tabular data in 2026)**, SVMs, k-NN, k-means, PCA
- Evaluation metrics: accuracy vs. precision/recall/F1, ROC-AUC, calibration, why accuracy lies on imbalanced data
- Feature engineering and why DL partially (not fully) automates it

### Resources
- Andrew Ng — *Machine Learning Specialization* (Coursera)
- *An Introduction to Statistical Learning* (free, with Python labs)
- StatQuest (YouTube) for intuition on any single concept

### Milestone
Take a messy real-world tabular dataset (e.g., from Kaggle), do a full pipeline: EDA → cleaning → features → 3+ models compared with proper cross-validation → error analysis writeup. Beat a naive baseline convincingly and *explain why* the winner won.

---

## Stage 2 — Neural Networks from Scratch (3–4 weeks)

The stage that separates people who *use* DL from people who *understand* it.

### Learn
- The perceptron → multilayer perceptron (MLP)
- Forward propagation as composed matrix multiplications + nonlinearities
- Activation functions: sigmoid, tanh, ReLU, GELU, SiLU/Swish — and *why* nonlinearity is required at all
- **Backpropagation** — derive it fully by hand for a 2-layer network; understand it as the chain rule applied over a computational graph
- Loss functions: MSE, cross-entropy (and its relationship to maximum likelihood and KL divergence)
- Weight initialization (Xavier/Glorot, He) and why bad init kills training
- Vanishing/exploding gradients
- Automatic differentiation: forward vs. reverse mode — what autograd actually does

### Resources
- **Andrej Karpathy — *Neural Networks: Zero to Hero*** (YouTube) — the single best resource in existence for this stage; build micrograd and makemore alongside him
- Michael Nielsen — *Neural Networks and Deep Learning* (free online book)
- Karpathy's micrograd repo

### Milestone
Build your own **micrograd-style autograd engine** (~150 lines of Python) and train an MLP on MNIST with it. Then write a blog post explaining backprop to a beginner. If you can't explain it, you don't know it.

---

## Stage 3 — Frameworks & the Craft of Training (4–5 weeks)

### Learn
- **PyTorch** (the field's lingua franca): tensors, autograd, `nn.Module`, `DataLoader`/`Dataset`, GPU usage, saving/loading, `torch.compile`
- Know that **JAX** exists (functional, used heavily in research/Google ecosystems) — learn it later if needed
- **Optimizers:** SGD + momentum, RMSProp, Adam, **AdamW** (the 2026 default), and newer entrants worth knowing: Lion, Sophia, **Muon** (used in several 2025–26 frontier training runs), Shampoo/SOAP
- **Learning-rate schedules:** warmup, cosine decay, one-cycle — LR is the single most important hyperparameter
- **Normalization:** BatchNorm, **LayerNorm**, RMSNorm — what they fix and where each is used
- Regularization in DL: dropout, weight decay, label smoothing, **data augmentation**, mixup/cutmix
- **The training debugging loop:** overfit a single batch first, monitor gradient norms, learn to read loss curves like an ECG
- Experiment tracking: Weights & Biases or MLflow; config management; reproducibility (seeds, determinism)
- Mixed-precision training (fp16/**bf16**), gradient accumulation, gradient clipping

### Resources
- Official PyTorch tutorials + *Deep Learning with PyTorch* book
- Karpathy — *A Recipe for Training Neural Networks* (blog post — read it 3 times)
- fast.ai — *Practical Deep Learning for Coders* (top-down complement)

### Milestone
Train an image classifier on CIFAR-10 to **>94% accuracy** with a from-scratch training loop (no high-level trainer): augmentation, LR schedule, W&B logging, ablation table showing what each trick contributed.

---

## Stage 4 — Core Architectures (5–6 weeks)

### Learn
**Convolutional networks (vision):**
- Convolution, pooling, receptive fields, feature hierarchies
- The historical arc (know it, don't dwell): LeNet → AlexNet → VGG → **ResNet (skip connections — a genuinely important idea)** → EfficientNet → **ConvNeXt** (CNNs modernized to compete with Transformers)
- Transfer learning and fine-tuning — how 95% of practical vision work is done
- Tasks beyond classification: object detection (YOLO family, DETR), semantic/instance segmentation (U-Net, Mask R-CNN, **SAM/SAM-2** — Segment Anything)

**Sequence models:**
- RNNs, LSTMs, GRUs — understand them conceptually and their failure mode (sequential bottleneck, long-range forgetting); they motivate everything that folled
- Encoder–decoder (seq2seq) and the original **attention** mechanism (Bahdanau) — attention as learned, content-based routing

**Embeddings:**
- word2vec/GloVe → the general idea of representation learning; contrastive learning (SimCLR, **CLIP**)

### Resources
- Stanford **CS231n** (vision) — lectures + assignments
- *Dive into Deep Learning* (d2l.ai) — free, code-first, excellent
- distill.pub archive for visual intuition

### Milestone
Two small projects: (1) fine-tune a pretrained ResNet/ConvNeXt on a custom dataset you collect yourself (~1–2k images) and deploy it behind a simple API; (2) build a character-level LSTM language model from scratch and sample text from it.

---

## Stage 5 — Transformers & Large Language Models (6–8 weeks)

The center of gravity of the entire field. Go deep here.

### Learn
**The architecture (implement, don't just read):**
- Self-attention: queries, keys, values; scaled dot-product; **multi-head attention**
- Positional encoding: sinusoidal → learned → **RoPE (rotary — the 2026 standard)** → ALiBi
- The full block: attention + MLP + residuals + pre-LayerNorm
- Encoder-only (BERT-style), decoder-only (GPT-style — the dominant paradigm), encoder-decoder (T5)
- **KV caching** — why inference works the way it does
- Attention variants: multi-query (MQA), **grouped-query (GQA)**, sliding-window, FlashAttention (the systems trick that made long context feasible), sparse/linear attention

**Tokenization:** BPE, SentencePiece, byte-level; why tokenization causes weird failures

**The modern LLM pipeline (know every step):**
1. **Pretraining** — next-token prediction at scale; data curation/dedup/filtering (quality of data now matters more than raw quantity)
2. **Scaling laws** — Kaplan → **Chinchilla** (compute-optimal training) → the 2025–26 shift to *inference-time* scaling
3. **Supervised fine-tuning (SFT)** — instruction tuning
4. **Preference alignment** — RLHF with PPO → **DPO** (direct preference optimization) → **GRPO** (the method behind DeepSeek-R1-style reasoning training) and RLVR (RL from verifiable rewards)
5. **Parameter-efficient fine-tuning:** **LoRA / QLoRA** — how everyone without a datacenter fine-tunes

**Mixture-of-Experts (MoE):**
- Sparse expert routing, load balancing; why nearly every 2025–26 frontier model (DeepSeek-V3, Llama 4, Mixtral lineage, most closed frontier models) is MoE — huge total parameters, small *active* parameters

**Multimodality:**
- Vision Transformers (**ViT**), CLIP-style contrastive pretraining
- Vision-language models: how images become tokens (projectors/adapters); LLaVA-style architectures
- Natively multimodal / "omni" models (text + image + audio + video in, multiple modalities out) — the 2026 default for frontier models

**Using LLMs well (practical layer):**
- Prompting, structured outputs, function/tool calling
- **RAG** (retrieval-augmented generation): embeddings, vector databases, chunking, reranking, evaluation — and when long-context beats RAG
- **Agents:** tool use loops, planning, memory, multi-agent orchestration, **MCP (Model Context Protocol)** for tool integration; agentic coding
- LLM evaluation: benchmarks and their contamination problems, LLM-as-judge, building your own evals (an underrated, highly employable skill)

### Resources
- **Karpathy — "Let's build GPT from scratch" + "Let's reproduce GPT-2" (nanoGPT)** — non-negotiable
- *Attention Is All You Need* + Harvard's *The Annotated Transformer*
- Stanford **CS224n** (NLP) and **CS336** (Language Modeling from Scratch — build an LLM end-to-end)
- Hugging Face courses (Transformers, and their alignment/RL material)
- Papers: GPT-2/3, LLaMA series, Chinchilla, InstructGPT, DPO, DeepSeek-V3 & R1 technical reports (the R1 report is the best public documentation of reasoning-model training)

### Milestone
(1) Train a small GPT (nanoGPT-scale, ~10–100M params) on a dataset of your choice from scratch; (2) fine-tune an open model (Llama/Qwen/Gemma class) with QLoRA on a task you care about, align it with DPO on a small preference set, and **build an eval harness** that proves your fine-tune beat the base model.

---

## Stage 6 — Generative Models (4–6 weeks)

### Learn
- **Autoencoders → VAEs:** latent variables, the ELBO, reparameterization trick
- **GANs:** the adversarial game, mode collapse; mostly superseded for images but the adversarial *idea* recurs everywhere (know StyleGAN historically)
- **Diffusion models (the dominant image/video/audio paradigm):**
  - Forward noising / learned denoising; DDPM → DDIM; score-based view (SDEs)
  - **Latent diffusion** (Stable Diffusion's key trick), classifier-free guidance
  - Conditioning and control: ControlNet, adapters
  - **Diffusion Transformers (DiT)** — the backbone of modern video generation (Sora-class models)
- **Flow matching / rectified flows** — the cleaner, faster successor to diffusion training, used in current frontier image models (Flux, SD3-class) and increasingly elsewhere
- Consistency models & few-step distillation (real-time generation)
- Autoregressive image/audio generation, discrete tokenizers (VQ-VAE), and speech models (TTS/ASR — Whisper-class)
- **Video generation** (2025–26 boom): temporal consistency, physics plausibility, world-model connections
- Evaluation of generative models: FID and its flaws, human eval, precision/recall for generation

### Resources
- Lilian Weng's blog — *What are Diffusion Models?* (and her whole blog, honestly)
- *Understanding Deep Learning* — Simon Prince (free PDF, superb on generative models)
- Hugging Face Diffusers course; papers: DDPM, Latent Diffusion, DiT, Flow Matching (Lipman et al.)

### Milestone
Implement DDPM from scratch on MNIST/CIFAR (unconditional → class-conditional with classifier-free guidance). Then fine-tune a Stable-Diffusion-class model with LoRA/DreamBooth on your own concept.

---

## Stage 7 — Specialized Domains (pick 2–3, 4–8 weeks)

Choose based on where you want to work. Each is a career-sized rabbit hole.

- **Graph Neural Networks (GNNs):** message passing, GCN/GAT/GraphSAGE, graph transformers; applications: molecules, recommender systems, traffic, knowledge graphs. *(Library: PyTorch Geometric; course: Stanford CS224W.)*
- **Deep Reinforcement Learning:** MDPs, Q-learning → DQN, policy gradients → PPO, actor–critic, offline RL, model-based RL. In 2026 RL matters most as (a) the engine of LLM reasoning training and (b) robotics. *(Resources: OpenAI Spinning Up, David Silver's lectures, CleanRL.)*
- **AI for Science:** AlphaFold-class structure prediction, **physics-informed neural networks (PINNs)**, **neural operators** (FNO) for PDEs, ML weather models (GraphCast, GenCast — now beating traditional forecasting), materials discovery (GNoME-style), neural simulation surrogates. One of the highest-impact directions this decade.
- **Time series & forecasting:** classical baselines (ARIMA, Prophet — often hard to beat!), N-BEATS/N-HiTS, PatchTST, **time-series foundation models** (TimesFM, Chronos-class zero-shot forecasters).
- **Audio & speech:** ASR (Whisper), neural TTS, audio codecs, real-time voice-to-voice models.
- **Embodied AI / robotics:** **vision-language-action (VLA) models** (RT-2, π0/OpenVLA lineage), imitation learning, diffusion policies, sim-to-real. Arguably the hottest frontier of 2026.
- **Geospatial / remote sensing:** satellite imagery models, geospatial foundation models (Prithvi, Clay, SatMAE lineage) — *relevant to the problem statement accompanying this roadmap.*
- **Recommendation systems, tabular DL, medical imaging** — deep, employable niches.

### Milestone
One substantial project in a chosen domain that uses domain-specific architectures — e.g., molecular property prediction with a GNN, a PPO agent that solves a Gym environment suite, or land-cover segmentation from Sentinel-2 imagery.

---

## Stage 8 — Scaling, Efficiency & Systems (4–6 weeks)

What separates hobbyists from people who ship. Increasingly, *the* hiring differentiator.

### Learn
- **GPU mental model:** memory bandwidth vs. compute (arithmetic intensity), why attention is memory-bound, roofline thinking; read Horace He's *Making Deep Learning Go Brrrr*
- **Distributed training:** data parallelism (DDP), **ZeRO/FSDP**, tensor parallelism, pipeline parallelism, context parallelism — what each shards and when you need it
- **Inference optimization:** KV-cache management (**PagedAttention/vLLM**), continuous batching, **speculative decoding**, prompt/prefix caching
- **Model compression:** quantization (int8, **4-bit: GPTQ/AWQ/NF4**, FP8/FP4 training), pruning, **distillation** (how small 2026 models get frontier-level: trained on frontier-model outputs)
- **Efficient kernels:** what FlashAttention actually does; Triton for custom kernels (optional but powerful)
- Edge/on-device deployment: ONNX, TensorRT, llama.cpp/GGUF, ExecuTorch
- **MLOps:** data versioning, CI for models, monitoring & drift detection, shadow deployment, feature stores; the unglamorous 80% of real ML work
- Cost math: estimating training/inference FLOPs and dollars before you start

### Resources
- Hugging Face *Ultra-Scale Playbook* (distributed training)
- vLLM & FlashAttention papers; Chip Huyen — *Designing Machine Learning Systems* and *AI Engineering*

### Milestone
Take your Stage-5 fine-tuned model and: quantize it to 4-bit, serve it with vLLM, benchmark latency/throughput/quality vs. the fp16 original, and write up the tradeoff table. Bonus: multi-GPU FSDP training run of your nanoGPT.

---

## Stage 9 — The 2025–2026 Frontier (ongoing)

What "latest advancements" actually means right now. You can engage with these seriously once Stages 5–8 are solid.

### 1. Reasoning models & test-time compute — *the defining shift*
- Models "think before answering" (long chain-of-thought), trained with **RL on verifiable rewards** (math/code correctness) — the o1/o3 → DeepSeek-R1 → 2026-default lineage; by 2026 every frontier model reasons by default
- **Inference-time scaling laws**: spending compute at inference (longer thinking, search, self-consistency, best-of-N with verifiers) as the successor to pure pretraining scaling
- Process reward models vs. outcome reward models; the (un)faithfulness of chain-of-thought
- Distilling reasoning into small models

### 2. Post-Transformer & hybrid architectures
- **State space models: Mamba/Mamba-2** — linear-time sequence modeling via selective state spaces
- **Hybrid attention–SSM models** (Jamba, Zamba, Nemotron-H lineage) — the pragmatic 2026 answer for long context
- Linear-attention revival (GLA, DeltaNet, Gated DeltaNet), sparse state expansion, log-linear attention
- **Titans / nested-learning-style architectures** — neural long-term memory that learns *at test time*; memory as a first-class architectural component
- Test-time training (TTT) layers

### 3. World models & video-as-simulation
- Genie-class interactive world models: generate playable, physics-consistent environments from prompts; JEPA-style predictive representations (V-JEPA)
- Used as training grounds for embodied agents and as a hypothesized path to physical-world understanding — 2026's most-watched research race (see [World Models Race 2026](https://introl.com/blog/world-models-race-agi-2026) and the [2026 world-models survey](https://arxiv.org/pdf/2606.00133))
- Model-based RL grows up: Dreamer-class agents, MuZero lineage

### 4. Agents as the product layer
- Long-horizon autonomous task execution (agentic coding is the flagship domain)
- Tool ecosystems (**MCP**), computer use, browser agents, multi-agent systems
- **Continual learning & persistent memory** for agents — moving past "goldfish" models; a named 2026 priority for major labs
- Agent evaluation & reliability engineering (the hard, employable part)

### 5. Efficiency & the small-model counter-trend
- Frontier-distilled small models (1–30B) matching last year's giants; on-device AI
- MoE everywhere; FP8/FP4 training; extreme context lengths (1M+ tokens, with subquadratic architectures pushing further)

### 6. Embodied AI
- VLA foundation models for robots; large-scale cross-embodiment datasets; dexterity and humanoid platforms; sim-to-real via world models

### 7. AI for science accelerating
- Weather/climate (GenCast-class probabilistic forecasting), protein & drug design, materials, math (formal theorem proving with LLMs + Lean), scientific agents that design/run experiments

### How to follow the frontier (see Stage 11 for habits)
Read the technical reports of each frontier release (DeepSeek, Qwen, Llama, Claude, GPT, Gemini families), not the press coverage.

---

## Stage 10 — Trust: Interpretability, Robustness, Alignment, Uncertainty (3–4 weeks + ongoing)

Deploying models that affect people requires this stage. It is also a fast-growing research/career niche.

### Learn
- **Mechanistic interpretability:** features & circuits, superposition, **sparse autoencoders (SAEs)** for extracting monosemantic features, activation patching, the logit lens; Anthropic's interpretability work is the canonical reading
- **Uncertainty quantification:** calibration (ECE, reliability diagrams), deep ensembles, MC dropout, **conformal prediction** (distribution-free guarantees — extremely useful in practice), aleatoric vs. epistemic uncertainty
- **Robustness:** adversarial examples & attacks (FGSM/PGD), distribution shift, out-of-distribution detection
- **LLM safety:** jailbreaks & prompt injection (the unsolved security problem of the agent era), hallucination measurement & mitigation, red-teaming
- **Alignment fundamentals:** reward hacking, sycophancy, scalable oversight, constitutional AI, model evaluations for dangerous capabilities
- Fairness, privacy (differential privacy, membership inference), and the regulatory landscape (EU AI Act era)

### Milestone
Train SAEs on a small transformer's activations and find interpretable features; or build a conformal-prediction wrapper around any earlier project and validate its coverage guarantee empirically.

---

## Stage 11 — Research Skills & Staying Current (permanent habit)

### Learn to read papers properly
- Three-pass method: (1) abstract/figures/conclusion, (2) method with margin questions, (3) re-derive or re-implement
- Reproduce at least one paper per quarter — reproduction is the fastest deep-learning teacher there is

### Build a filtering system (the field produces ~100s of papers/day)
- **Follow:** arXiv cs.LG/cs.CL/cs.CV via a filter tool (alphaXiv, Papers with Code successors, arxiv-sanity lineage)
- **Blogs/newsletters:** Lilian Weng, Sebastian Raschka's *Ahead of AI*, Interconnects (Nathan Lambert), Chip Huyen, lab blogs (Anthropic, DeepMind, Meta AI)
- **Karpathy's channel** and lectures for canonical explanations
- **Conferences to skim:** NeurIPS, ICML, ICLR, CVPR, ACL — read best-paper lists and orals
- Technical reports of frontier models (the richest public documentation of what actually works at scale)

### Do research
- Pick a small question → run a controlled experiment → write it up honestly (negative results included) → publish as blog post or workshop paper
- Contribute to open source (Hugging Face ecosystem, vLLM, PyTorch, Axolotl/TRL) — the highest-signal resume line that isn't a paper

---

## The mindset rules (read when discouraged)

1. **Implementation beats intuition beats memorization.** If you haven't coded it, you don't know it.
2. **Baselines first, always.** A logistic regression / gradient-boosting baseline is the honest yardstick for any deep model.
3. **Look at your data.** More projects die from data bugs than architecture choices. EDA is not optional.
4. **Overfit one batch first.** The universal sanity check for any training pipeline.
5. **The field moves fast, but fundamentals move slowly.** Attention, backprop, optimization, probability — the 2026 frontier is built from the same bricks as 2016. Invest in bricks.
6. **Compute is a constraint, not an excuse.** Karpathy trained GPT-2 for ~$20 in 2024. Colab/Kaggle/cheap cloud GPUs are enough for every milestone above except frontier pretraining.
7. **Ship things.** A deployed, documented, slightly-scruffy project beats a perfect private notebook.

---

*Companion document: [`PROBLEM_STATEMENT.md`](./PROBLEM_STATEMENT.md) — a real-world unsolved problem that exercises nearly every stage of this roadmap, with a structured approach manual.*
