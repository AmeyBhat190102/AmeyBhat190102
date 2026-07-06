# The Model Training Mastery Track

> **Goal:** you can take *any* model — any architecture, any modality, any scale that fits your compute — and pretrain it, continue-pretrain it, fine-tune it fully or parameter-efficiently, align it, surgically modify it (swap its vocabulary, graft layers, extend its context, merge it with another model, distill it, prune it), and *diagnose it when it breaks*. Not restricted to one recipe or one library: you understand training at the level where recipes are derivable, not memorized.
>
> **Structure:** Part A = the twelve competencies (summary + 🗣️ say-it-aloud checks, same protocol as the [roadmap](./ROADMAP.md)). Part B = **the Training Gauntlet**, twelve hands-on challenges with pass criteria. Part C = **the mastery problem statement** — a real, unsolved problem that forces every competency.
>
> **Prerequisites:** Roadmap Stages 0–5 (at least through 5.8). Run this track in parallel with Stages 6–8.
> **Compute:** everything in Parts A–B fits on one rented consumer/prosumer GPU (RTX 4090/A6000-class, or Colab Pro/Kaggle + occasional cheap cloud bursts). Mastery is demonstrated at small scale with correct *method*; scale is a budget, not a skill.

---

# Part A — The Twelve Competencies

## A1. The data engine

**Summary:** Training is data programming: the dataset is the program, the optimizer merely executes it. Competency means building corpus pipelines — collection, extraction (HTML/PDF → clean text), language ID, **deduplication** (exact + MinHash/LSH near-dedup), **quality filtering** (heuristics like Gopher rules; classifier-based scoring; perplexity filters), PII scrubbing, **contamination checks** against your evals — and then *mixing*: domain ratios, upsampling rare-but-valuable domains, multi-epoch decisions (small clean data can be repeated ~4 epochs before returns collapse), and data **curriculum/annealing** (frontier practice: end pretraining on the highest-quality slice, i.e. midtraining). For SFT, quality dominates quantity by orders of magnitude (LIMA); for RL, the dataset is prompts + a reward definition, and its difficulty distribution decides whether learning happens at all.

🗣️ **Say it aloud:**
- Why does near-duplicate text hurt *twice* (wasted compute + memorization/regurgitation risk)? How does MinHash find near-dupes in a billion documents without O(n²) comparisons?
- You have 10B tokens of clean domain text and a 100B-token budget. Repeat epochs, mix with general web text, or synthesize more? Argue the tradeoffs aloud and name what you'd measure.
- What is data annealing / midtraining? Why does *ending* on high-quality data matter more than starting with it? (Recency of gradient updates.)
- How would you check whether MMLU leaked into your corpus, including *paraphrased* leakage?
- Why can a difficulty-mismatched prompt set make GRPO learn nothing? (All samples correct or all wrong → zero advantage signal.)
- What makes synthetic data collapse a real risk, and what's the standard mitigation? (Grounding in verified/filtered outputs, mixing with real data.)

## A2. Tokenizers & vocabularies — full command

**Summary:** The tokenizer is a frozen contract between data and model; competency means being able to *renegotiate* it. Train BPE/Unigram tokenizers from raw text (vocab size tradeoffs: bigger = shorter sequences but bigger embedding tables and rarer-token undertraining); measure **fertility** (tokens/word) per language/domain; understand byte fallback, special tokens, chat-template tokens, and digit handling. The surgical skills: **vocabulary extension** (append new tokens, initialize their embeddings) vs **full transplant** (replace the tokenizer entirely and rebuild both the input embedding matrix and the output/LM head — tied or untied). Naive random init of new embeddings destroys the model until massive retraining; smart initialization (mean of the old-token pieces each new token maps to; FOCUS/WECHSEL-style similarity-weighted combinations) preserves most capability from step zero. This competency is the heart of Problem Statement #2.

🗣️ **Say it aloud:**
- Walk through training a BPE tokenizer from scratch: what's the starting alphabet, what's the loop, when do you stop?
- Vocab 32k vs 256k: name four consequences (sequence length, embedding parameters, softmax cost, rare-token training signal).
- You append 8,000 Devanagari-native tokens to a Llama-class model. Describe *exactly* what tensors change shape, and three initialization strategies for the new rows, best to worst.
- Why must the LM head change too, and what does weight tying imply for the surgery?
- After a full transplant, which parts of the model are "confused" and which are untouched? Therefore, what should the warm-up training phase freeze and unfreeze, in what order?
- How do you *prove* a transplant preserved capability — what's the honest eval before/after, at matched token counts?

## A3. Objectives & losses

**Summary:** What you train *toward*. Causal LM (next token — the workhorse), masked LM (BERT), span corruption (T5), prefix-LM; **multi-token prediction** (predict several future tokens with auxiliary heads — DeepSeek-V3 uses it; densifies signal and enables self-speculative decoding); contrastive objectives (CLIP/embedding models); distillation losses (KL on teacher logits, temperature-scaled; hidden-state/attention matching); auxiliary stabilizers (MoE load-balancing loss, z-loss on the softmax normalizer, embedding-norm regularizers). Loss masking (SFT prompts, padding) and sequence **packing** (concatenate short examples; mask attention across boundaries or accept the noise deliberately) are everyday craft.

🗣️ **Say it aloud:**
- Why does causal LM training extract a learning signal from *every* token position in parallel, and why is that data efficiency the paradigm's superpower?
- What does temperature do in distillation KL, and why does higher T transfer "dark knowledge" (relative wrongness among incorrect classes)?
- You pack 10 short SFT examples into one 4k sequence. What goes subtly wrong without cross-example attention masking, and when is it acceptable anyway?
- What is z-loss for, mechanically? What numerical pathology does it prevent at scale?

## A4. Optimization at depth

**Summary:** Beyond Stage 3.2: the AdamW hyperparameters that actually matter (β2 and ε interact with gradient noise — long-tail token distributions want β2≈0.95 at scale, not 0.999); weight-decay-what (decay matrices; don't decay norms/embeddings/biases); LR as a function of model size (bigger models want smaller LRs) and **µP (maximal update parametrization)** — parametrize so optimal LR *transfers* across widths, letting you tune small and train big (used in real frontier runs); batch-size scaling via the **critical batch size / gradient-noise-scale** framing; schedules beyond cosine (warmup-stable-decay so you can branch/anneal from one long run); **loss-spike forensics** — the frontier-documented playbook: skip the bad batch, restart from checkpoint before the spike, tighten clipping, lower LR, check for data poison; fp8 training and its scaling tricks. This is the competency that makes you unafraid of *any* training run.

🗣️ **Say it aloud:**
- Why does β2=0.999 cause instability at large scale with rare tokens? (Second-moment estimate lags a sudden large gradient → oversized step.)
- Explain µP's promise in one sentence, and why naive parametrization makes optimal LR shrink with width.
- What is the gradient noise scale and how does it define "critical batch size"? What happens to sample efficiency past it?
- Give the loss-spike triage playbook aloud, in order, with the reasoning for each step.
- Why warmup-stable-decay instead of cosine for a lab that trains many model sizes off one run? (Branch points; no need to fix total steps in advance.)
- What breaks first in fp8 training and what do per-tensor scaling factors fix?

## A5. Initialization, stability & architecture-for-trainability

**Summary:** Deep stacks amplify everything; competency is knowing the stabilizer toolkit and *why each exists*: pre-norm blocks; residual-branch scaling at init (scale output projections by 1/√(2·n_layers) so the residual stream's variance stays bounded); **qk-norm** (normalize queries/keys to stop attention-logit explosion — common in 2025–26 models); z-loss; embedding LR multipliers; careful handling of the softmax and norm layers in low precision. Also: reading a config file like a pro — given any Hugging Face `config.json`, you can reconstruct the parameter count and memory footprint on paper.

🗣️ **Say it aloud:**
- Why do the *output* projections of attention/MLP get down-scaled at init in deep transformers? Trace residual-stream variance across 80 layers aloud.
- What is attention-logit explosion, what does qk-norm do about it, and what visible training symptom does it fix?
- Take Llama-3-8B's rough config (d=4096, 32 layers, 32 heads/8 KV, ffn≈14336, vocab 128k): reconstruct ~8B parameters aloud. (You should be able to do this for *any* config.)
- Which layers are traditionally kept in fp32 even in bf16 training, and why?

## A6. Fine-tuning: full FT vs PEFT — and catastrophic forgetting

**Summary:** The decision science of adaptation. **Full FT**: maximum capacity change, maximum forgetting risk, ~16 bytes/param of training memory. **LoRA/DoRA**: low-rank updates on chosen projections (attention-only vs all-linear matters; all-linear at modest rank usually wins); rank/α/dropout/LR heuristics (LoRA wants ~10× the full-FT LR); **QLoRA** internals (NF4 — information-theoretically optimal 4-bit for normal-ish weights; double quantization; paged optimizers). When full FT wins: large distribution shift, new modality/language, when you'll serve the merged model anyway and can afford it. **Catastrophic forgetting** is the tax on all of it; mitigations: replay (mix ~1–5% general data into domain training — the single most effective practical trick), lower LR, fewer epochs, freezing schedules, KL-anchoring to the base model, and *measuring* forgetting with a held-out general suite rather than hoping.

🗣️ **Say it aloud:**
- Decision drill — answer instantly with reasoning: (a) 7B model, 500 support-chat examples; (b) 70B model, one 24GB GPU, legal-domain adaptation; (c) new programming language with 2B tokens of code; (d) new *natural* language with different script. Full FT, LoRA, QLoRA, or continued pretraining + transplant?
- Why do LoRA and full FT diverge most on tasks far from pretraining distribution? What does the low-rank constraint deny you?
- Explain NF4 in two sentences: what distribution assumption, what does "information-theoretically optimal" mean here?
- How exactly does replay data prevent forgetting, mechanistically? (Gradients keep pulling toward the old distribution's minima.)
- Design aloud the eval that *detects* forgetting before your users do.

## A7. Continued pretraining & domain/language adaptation

**Summary:** The middle path between fine-tuning and from-scratch: take a strong base model and push billions of new-domain tokens through the causal LM objective. The craft: **LR re-warming** (restart warmup, peak well below original peak — too high erases, too low doesn't adapt), replay ratio of original-distribution data (1–5% typically), data ordering (easy/general → hard/specific), deciding *what to freeze* (embeddings-only warm-up phases after vocabulary changes), and knowing the **stability–plasticity tradeoff** is the fundamental dial you're turning. This is how domain models (code, medicine, law, new languages) are actually built in 2026 — few train from scratch.

🗣️ **Say it aloud:**
- Why re-warm the LR at all instead of continuing the decayed schedule? And why is the *original peak* LR usually catastrophic?
- Sketch the loss curves you'd expect on (a) new-domain validation and (b) original-distribution validation during healthy continued pretraining. What does divergence between them tell you?
- Continued pretraining vs LoRA for adding 5B tokens of Sanskrit: why is PEFT structurally insufficient here?
- What experiment tells you your replay ratio is too low? Too high?

## A8. Model surgery

**Summary:** The competency that makes "any model, any modification" literal. **Freezing schedules & layer-wise LR decay** (early layers general, late layers specific). **Head grafting**: replace/add task heads, reuse the trunk. **Depth up-scaling** (SOLAR-style: duplicate middle layers, heal with continued training) and width expansion (Net2Net-style function-preserving growth). **Long-context extension**: RoPE scaling — position interpolation, NTK-aware scaling, **YaRN** — plus a healing run on long documents; know why each works via RoPE frequency geometry. **Attention surgery**: MHA→GQA conversion (mean-pool KV heads, heal briefly). **Vocabulary transplant** (A2). **Model merging**: weight averaging/SLERP, task vectors (add/subtract fine-tune deltas), TIES/DARE (resolve sign conflicts, drop-and-rescale) — free lunch surprisingly often, and understanding *why it works at all* (linear mode connectivity of fine-tunes from a shared base) is real understanding. **Distillation** as surgery: teacher→student across sizes and even architectures (transformer→Mamba distillation exists). **Pruning + healing**: structured removal (layers, heads, width) then short retraining — how several production "mini" models are made.

🗣️ **Say it aloud:**
- Why does duplicating layers 8–24 of a 32-layer model produce something *nearly* functional immediately? (Residual stream: layers write small updates to a shared stream, so repeats ≈ gentle re-application.) Why "nearly," and what does healing fix?
- Explain position interpolation vs NTK-aware vs YaRN in terms of what each does to RoPE frequencies — which positions/frequencies does each preserve or squash?
- Why does averaging two fine-tunes of the *same* base often work, while averaging two independently-trained models fails utterly? (Permutation symmetry / shared basin.)
- What are task vectors? "Chat-ness minus base equals a direction you can add to a different fine-tune" — when does this arithmetic hold and when does it break?
- MHA→GQA conversion: what exactly do you average, what breaks temporarily, how long is the heal?
- You must shrink a 9B model to 6B for a latency SLA. Pruning+healing vs distillation-from-scratch vs training a 6B: what decides, and what would you try first?

## A9. Post-training: SFT → preference optimization → RL, end to end

**Summary:** Running the full alignment pipeline yourself, not describing it. **SFT**: data curation over volume, chat templates, loss masking, packing, multi-epoch decisions, checkpoint selection by *downstream* evals (not SFT loss — they decorrelate). **Reward models**: Bradley–Terry pairwise training, and their failure modes (length bias, style-over-substance). **DPO** in practice: β (KL-ish strength), the chosen-*and*-rejected-likelihood-drop phenomenon, reference-model role, variants (IPO's overfitting fix, KTO's unpaired data, ORPO's reference-free single stage, SimPO). **GRPO/RLVR**: sample groups per prompt, verify (unit tests, math checkers, string match — and their gameability), group-normalized advantages, no value network; the practical failure zoo — reward hacking (passing tests via special-casing), entropy/diversity collapse, length inflation, KL runaway; curriculum by difficulty so the group has reward *variance*. Know when each stage is even needed: many production tasks stop at SFT.

🗣️ **Say it aloud:**
- Why does DPO training *lower* the likelihood of chosen responses too (only the margin grows), and why doesn't that necessarily hurt?
- What does β control in DPO, and the symptom of each extreme?
- In GRPO, why does a prompt where all 8 samples succeed contribute *zero* gradient? Derive the group-normalized advantage aloud. What does that imply about dataset difficulty curation?
- Name three concrete ways a model hacks a unit-test reward and a countermeasure for each.
- Your DPO'd model's responses got 40% longer with no quality gain. What happened (length-biased preferences) and two fixes.
- Why can excessive SFT on distilled reasoning traces *hurt* subsequent RL? (Mode collapse onto teacher style; entropy too low to explore.)

## A10. Evaluation & training diagnostics

**Summary:** You cannot train what you cannot measure. Perplexity: comparable only under identical tokenizers (per-*byte* metrics for cross-tokenizer comparisons — critical after transplants); the eval hierarchy (loss → benchmarks → task evals → human/LLM-judge evals) and their decorrelation as models specialize; contamination discipline; checkpoint selection; **ablation discipline** (one change at a time, multiple seeds at small scale, matched token budgets — the most common fraud-on-yourself is comparing runs with different compute); and reading training telemetry like an ECG: loss, gradient norm, weight norm, activation stats, expert-routing entropy, generation samples every N steps.

🗣️ **Say it aloud:**
- Why is perplexity meaningless across different tokenizers, and what's the fix? Why does this matter *specifically* for a vocabulary-transplant project?
- SFT loss down, downstream evals flat or worse — three distinct explanations and the test for each.
- Design the telemetry dashboard for a 30-day continued-pretraining run: name every panel and the pathology it exists to catch.
- What makes an ablation *believable*? List the checklist aloud (matched tokens, matched tuning effort, ≥2 seeds, held-out eval, no peeking).

## A11. Scale mechanics (hands-on distributed training)

**Summary:** Roadmap 8.2, but drilled until muscle memory: DDP → **FSDP** (wrapping policies, sharding strategies, mixed-precision configs) → when tensor/pipeline parallelism become necessary; activation checkpointing (trade 30% compute for huge activation-memory savings); gradient accumulation correctness (loss normalization, RNG, timing of clipping); deterministic **checkpoint-resume** (model + optimizer + scheduler + dataloader/RNG state — resume must reproduce the loss curve, bit-for-bit-ish); throughput accounting (tokens/sec, MFU%) and finding the bottleneck (data loading? communication? kernel efficiency?).

🗣️ **Say it aloud:**
- Your FSDP run resumes from checkpoint and the loss jumps 0.3. Name four state components people forget to save, in order of likelihood.
- Where exactly in the step does gradient clipping go with accumulation (after accumulate, before step) and why?
- Activation checkpointing: what's stored, what's recomputed, what's the compute overhead, and when is it a no-brainer?
- Your MFU is 12%. Walk the diagnosis tree aloud: what do you measure first, second, third?

## A12. Cross-modality transfer of training skill

**Summary:** Proof of generality: the same competencies drive non-LLM training. Fine-tune **diffusion models** (LoRA on cross-attention; DreamBooth's prior-preservation loss to stop concept bleed; ControlNet's zero-initialized conv trick — a beautiful stability idea: new conditioning starts as an exact no-op); fine-tune **Whisper-class ASR** (spectrogram frontends, CTC vs seq2seq, low-resource-language adaptation — a direct rehearsal for Problem Statement #2's spirit); fine-tune **ViTs/detection models**; train small **RL policies** (PPO on gym tasks — reward curves are a different literacy worth having). After this, "I can train transformers" upgrades to "I can train models."

🗣️ **Say it aloud:**
- Why does DreamBooth need prior-preservation images — what forgetting phenomenon is it countering, and how is that *the same* phenomenon as A6's replay?
- Why is ControlNet's zero-init conv the same *idea* as LoRA's zero-init B matrix and residual-scaling at init? State the shared principle in one sentence. ("New capacity must start as identity/no-op so it can't damage what works.")
- What changes and what stays the same in your training-debug playbook when the model is a diffusion UNet instead of a causal transformer?

---

# Part B — The Training Gauntlet

Twelve challenges, roughly ordered. Each has a **pass criterion** — objective, checkable, portfolio-ready. Do them on small models (0.1B–3B class unless noted); write up every one (what you did, what broke, what you measured). Completing all twelve is this track's milestone. Expect G1–G6 ≈ 6–8 weeks, G7–G12 ≈ 8–10 weeks alongside roadmap stages.

| # | Challenge | Pass criterion |
|---|---|---|
| **G1** | **Overfit-one-batch, three ways.** Overfit a single batch with (a) an MLP, (b) a small ViT, (c) a small GPT — from-scratch loops. | All three reach ~zero loss; you can state each family's characteristic failure you hit and fixed. |
| **G2** | **Tokenizer + tiny GPT from scratch.** Train BPE tokenizers (8k/32k/64k) on one corpus; train the same ~25M-param GPT on each. | A plot of loss-per-**byte** (not per-token!) vs vocab size, with a paragraph explaining the result. |
| **G3** | **Micro scaling law.** Train 5 model sizes (~1M→~60M) on fixed data; fit L(N) power law; extrapolate to a size you *then actually train*. | Extrapolated loss within ~5% of the real run. You have now *touched* a scaling law. |
| **G4** | **The adaptation bake-off.** Same task, same base model: full FT vs LoRA (2 ranks) vs QLoRA. Measure task quality AND general-capability retention (forgetting suite) AND memory/time. | A 5-row table with all three axes; a written recommendation with conditions. |
| **G5** | **Vocabulary extension.** Add 5–10k domain/language tokens to a small open model; initialize smart (subword-mean) vs random; brief embedding-only warm-up, then unfreeze. | Smart-init demonstrably beats random-init at matched tokens; fertility improvement quantified; no general-capability regression beyond a stated budget. |
| **G6** | **Full vocabulary transplant.** Replace a small model's tokenizer entirely (e.g., English BPE → byte-level or a new-language tokenizer); rebuild embeddings + LM head; heal with staged unfreezing. | Per-byte perplexity recovers to within ~10% of the original model on original-distribution text, and beats it on the new target distribution. *(The direct rehearsal for Part C.)* |
| **G7** | **Long-context extension.** Take a 4k/8k-context model to 32k+ via YaRN (compare against PI); heal on long documents. | Passkey/needle retrieval works at 32k; perplexity at original lengths degrades <2%. |
| **G8** | **Depth up-scaling + healing.** SOLAR-style layer duplication on a small model; measure immediately (broken-ish) and after healing. | Healed up-scaled model beats the original on your eval at matched *total* extra compute vs just continuing to train the original — or you honestly report it doesn't, and explain why. |
| **G9** | **The alignment pipeline, end to end.** SFT a base model → build a small preference set (self-generated pairs + your judgments or an LLM judge with audits) → DPO. Build the eval harness first. | Blind pairwise eval: DPO model > SFT model > base, with win rates and honest confidence intervals. |
| **G10** | **GRPO on verifiable rewards.** RL a small model (1–3B) on GSM8K-style math with a programmatic checker; group sampling, normalized advantages; watch for hacking/length inflation/entropy collapse — instrument all three. | Pass@1 improves meaningfully over the SFT starting point; your write-up shows the entropy and length curves and at least one pathology you caught and fixed. |
| **G11** | **Cross-modality double.** (a) LoRA/DreamBooth fine-tune a diffusion model on a concept with prior preservation; (b) fine-tune Whisper on a low-resource language/accent subset. | (a) Generates your concept without destroying the class prior; (b) WER improvement over base Whisper quantified on a held-out set. |
| **G12** | **Break it, then fix it.** Induce a loss spike / divergence on purpose (LR too high, poisoned batch, bad init — your choice); then recover using the A4 playbook; then make the run resumable and *prove* bit-consistent resume. | A write-up with the loss curves of the disaster, the diagnosis, the recovery, and a resume that reproduces the curve. The most valuable artifact in the whole Gauntlet for interviews. |

**Tooling note:** do G1–G3 with raw PyTorch loops (no trainers). From G4 on, you may use HF Transformers/TRL/PEFT/Axolotl — but you must be able to explain everything the library does for you. If you can't, drop down one abstraction level until you can.

---

# Part C — The Mastery Problem Statement

## Project **Bhasha-Setu** (भाषा-सेतु, "language bridge"): give a truly low-resource Indian language its first real LLM — by transplant, not from scratch

### The problem, in plain language

Frontier models in 2026 are decent in Hindi, passable in Bengali/Tamil/Marathi — and functionally useless in **Konkani, Bodo, Santali, Tulu, Dogri, Maithili, Kashmiri** and dozens of other languages with *millions* of speakers each (several are among India's 22 constitutionally scheduled languages). Useless in a specific, measurable way:

1. **Tokenizer tax:** existing tokenizers fragment these languages into 3–6× more tokens than English — meaning 3–6× less effective context, 3–6× higher cost, and systematically degraded generation quality. For scripts like Ol Chiki (Santali) it can degenerate to byte-level shrapnel.
2. **Data desert:** each has somewhere between 10M and a few hundred million tokens of digitizable text — far too little to pretrain from scratch (which needs hundreds of billions), which is *exactly why the from-scratch route is dead* and **surgical adaptation of an existing model is the only viable path**. This problem is structurally a model-training problem.
3. **No evaluation exists:** you cannot even *measure* progress today — there is no serious benchmark for most of these languages. Whoever builds the eval defines the field.
4. **Nobody's economics work:** frontier labs won't prioritize a 2M-speaker language; governments fund corpora but not competent training. The gap is real, persistent, and precisely the size of one skilled person with modest compute.

**Why this makes you a training master:** every single competency in Part A is load-bearing here — corpus engineering from scratch (A1), tokenizer training and full vocabulary transplant (A2), objective choices for a bilingual model (A3), continued pretraining with re-warming and replay (A4, A7), staged freezing and possibly depth up-scaling (A5, A8), the forgetting war on two fronts — don't lose English/Hindi *while* gaining the target language (A6), full SFT→DPO post-training with self-built data (A9), evaluation invented from nothing including cross-tokenizer per-byte metrics (A10), multi-GPU runs at the biggest scale you attempt (A11), and a Whisper-adaptation side quest for the language's speech (A12). There is no hiding place.

### The concrete goal

> Pick one genuinely low-resource language with a living community. Produce: **(1)** an open model (1–8B class) that speaks it usefully — measured, not vibed; **(2)** the first public evaluation suite for that language; **(3)** a distilled/quantized variant that runs on a budget phone; **(4)** a technical report documenting the recipe so the next person can repeat it for the next language.

This is a real contribution to the world, a publishable result (there are active venues: AmericasNLP/IndicNLP workshops, EMNLP/ACL findings), and the single most complete training portfolio piece that exists.

---

### The approach manual (scaffolding, not solution — the design decisions are deliberately left as *your* questions)

#### Phase 0 — Choose the language & find your speakers (1–2 weeks)
Pick by: (a) you or someone you can reach speaks it; (b) 10M–500M tokens plausibly gatherable; (c) nothing decent exists (verify: run existing models on it, document the failure — this becomes your paper's motivation section). Recruit 1–3 native speakers willing to judge outputs monthly; without them you will optimize translationese and never know.
**Key questions:** What script(s)? Is it code-mixed with Hindi/English in the wild (it is — how will you handle that: separate or embrace)? What dialects, and which do you target?
**Checkpoint:** a 2-page language dossier + documented failure gallery of existing models.

#### Phase 1 — The corpus engine (4–8 weeks; 40% of the total work)
Sources: Wikipedia + Common Crawl slices (language-ID is hard for close cousins — Konkani vs Marathi share script; you may need to *train a language classifier* first, a nice sub-project), news archives, government gazettes (India publishes in scheduled languages — a goldmine), literature past copyright, **OCR of scanned books** (Indic OCR is imperfect — quality-filter aggressively), radio/YouTube **ASR transcripts** (Whisper fine-tuned in G11(b)/A12 feeds this — the loop closes), and parallel corpora (Bible/legal texts translations exist for almost everything).
**Key questions:** What's your dedup + quality pipeline for a language you can't read fluently? (Speaker spot-checks on samples, statistical filters.) What's the ethical/licensing line for community text? How much parallel (target↔English/Hindi) data can you assemble — it disproportionately helps a bilingual model.
**Checkpoint:** a versioned corpus with a datasheet: token counts by source, dedup stats, quality-filter ablation on samples, contamination sweep against your (future) evals.

#### Phase 2 — Tokenizer study (1–2 weeks)
Train candidate tokenizers (sizes, BPE vs Unigram, with/without code-mixing data). Measure fertility on held-out target text *and* on English/Hindi (you must not wreck the donor languages). Decide: **extend** the donor model's vocabulary (safer, smaller surgery — likely right if the script is already semi-supported) vs **transplant** (maximal fertility win, maximal risk — right if the script is shattered to bytes). This decision — and your evidence for it — is one of the report's core contributions.
**Checkpoint:** fertility tables + the extend-vs-transplant decision memo, with predicted effective-context and cost improvements.

#### Phase 3 — Baselines & the evaluation suite (2–4 weeks; do *before* training)
Build the eval first or you'll fool yourself for months: per-**byte** perplexity on held-out target text (tokenizer-independent — A10); translated + **natively-authored** QA/reasoning items (translationese inflates scores — measure the gap, it's a finding); generation quality rubric scored blind by your native speakers; code-mix handling; and a **forgetting suite** (English/Hindi benchmarks) you run at every stage. Baseline every existing model (frontier APIs, open multilingual models like Qwen/Gemma/Llama, any IndicNLP models).
**Checkpoint:** public eval repo v1 + a baseline leaderboard. *(This alone is a citable artifact.)*

#### Phase 4 — Rehearsal at small scale (2–3 weeks)
Run the *entire* pipeline — surgery, healing, continued pretraining, SFT, eval — on a 0.5–1B model first. Every mistake costs 10× less here. Only scale the recipe once the small model shows the expected fertility gains, target-language perplexity trajectory, and bounded forgetting.
**Key questions:** What will you freeze first after surgery, and for how many tokens? (Embedding-only warm-up → gradual unfreeze — but *you* determine the schedule empirically.) What replay ratio of English/Hindi keeps the forgetting suite flat?
**Checkpoint:** small-scale recipe card with every hyperparameter and its justification.

#### Phase 5 — The main surgery + continued pretraining (4–8 weeks, your biggest compute spend)
Apply the recipe to your chosen base (a strong 4–8B open model; consider whether **depth up-scaling** (G8) pays before the big run — capacity for a new language is a real question). Continued pretraining over the full corpus with LR re-warming, data annealing (best data last), telemetry dashboard from A10 running throughout, checkpoints you can *actually* resume (G12).
**Key questions:** Multi-epoch over scarce data — how many before returns collapse? Curriculum: parallel data early (anchor the new language to known ones) or mixed throughout? What loss-spike playbook is pinned above your desk?
**Checkpoint:** the base "Bhasha" model + full training report: curves, spikes survived, forgetting-suite trajectory, ablations.

#### Phase 6 — Post-training with data you must invent (3–5 weeks)
There is no instruction data in your language. Bootstrap: translate strong open SFT sets (quality-filter the translations — bad MT poisons everything), **synthesize** with the strongest available frontier model *in-language* then filter hard (LLM-judge + native-speaker audits of samples), and hand-write a small gold set (a few hundred examples of you + speakers — LIMA says this matters more than you think). Then SFT → DPO (preferences from speaker judgments + audited LLM-judge). If the language has strong verifiable domains (math education in-language?), a small GRPO pass is the stretch goal.
**Checkpoint:** instruct model beating the Phase-5 base and all Phase-3 baselines on blind native-speaker pairwise eval, with win rates and CIs.

#### Phase 7 — Compression for the actual users (2–3 weeks)
The speakers of low-resource languages disproportionately use budget Android phones. Distill to a 1–3B student (sequence-level distillation from your own model — A8), quantize (4-bit GGUF), measure on-device tokens/sec and quality delta, ship a demo app or llama.cpp recipe.
**Checkpoint:** the model running on a real budget phone, on video, with the quality-vs-size table.

#### Phase 8 — Release & report (2 weeks)
Weights + tokenizer + eval suite + datasheet + recipe report, openly licensed. The report's honest core: what the transplant cost and bought (per-byte metrics!), the forgetting frontier you achieved, what you'd do differently, and the recipe card for language N+1.

---

### Traps, named now
1. **Translationese everywhere** — translated evals overestimate, translated SFT teaches stilted register. Natively-authored gold data is small but non-negotiable.
2. **Per-token metrics across tokenizer changes are lies.** Per-byte or nothing (A10). Reviewers *will* check.
3. **Winning the language, losing the model.** Run the forgetting suite at every checkpoint; a model that speaks Konkani but lost its reasoning is a failed transplant.
4. **Contaminating your own evals** — you built corpus and benchmark from the same small universe of text; sweep aggressively.
5. **Synthetic-data mode collapse** — frontier-generated SFT data in a language the frontier model is *weak* in is a photocopier of errors. Filter with native speakers or don't use it.
6. **Compute-blind ambition.** Budget with A4/8.6 math *before* Phase 5; a 4B recipe executed cleanly beats an 8B recipe you couldn't afford to debug.
7. **Solo-hero mode.** The native speakers are not annotators; they're co-authors. Treat them so.

### What success looks like
- **2 months in:** corpus + eval suite + baseline leaderboard (already a real contribution and a strong portfolio).
- **4–5 months in:** transplanted base model with documented fertility win and bounded forgetting — the technically hardest artifact.
- **7–8 months in:** instruct model preferred by native speakers, phone-deployed distillate, public release + report. At this point you have trained, surgically modified, aligned, distilled, and shipped a model family end to end — with evidence. That is what "I can retrain or fine-tune any model, including with a different vocabulary" looks like when it's true.
