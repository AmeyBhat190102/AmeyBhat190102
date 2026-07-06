# The Complete Deep Learning Roadmap (2026 Edition) — In-Depth

> A stage-by-stage path from fundamentals to the research frontier, current as of mid-2026.
> Every topic has a **summary** (what it is and why it matters) and **🗣️ Say-it-aloud questions** — your self-examination protocol. Answer them out loud, without notes, as if teaching a junior. If you stumble, hesitate, or hand-wave, the topic is not done. This is the Feynman technique operationalized; it is the fastest known way to convert exposure into mastery.

**Companion documents:**
- [`MODEL_TRAINING_MASTERY.md`](./MODEL_TRAINING_MASTERY.md) — the deep-dive track on training, retraining, fine-tuning, and surgically modifying *any* model (including vocabulary transplants, layer grafting, and full post-training pipelines), with its own problem statement.
- [`PROBLEM_STATEMENT.md`](./PROBLEM_STATEMENT.md) — the capstone applied problem (Himalayan GLOF early warning) that exercises the whole roadmap.

---

## The operating system for this roadmap

**The self-check protocol (do this for every topic):**
1. Study the topic (70% coding/deriving, 30% reading/watching).
2. Close everything. Answer the 🗣️ questions **aloud**. Record yourself if you can bear it.
3. Grade honestly: *fluent* (move on), *shaky* (re-derive on paper, retry tomorrow), *blank* (re-study differently — different resource, not the same one again).
4. Re-ask yourself the questions from the previous two stages once a week (spaced repetition). Mastery decays; interleaved review stops the decay.

**Pace:** ~12–18 months at 10–15 hrs/week to Stage 8; the pro-fast variant is 15–20 hrs/week with ruthless milestone discipline. Stages 9–11 are permanent.

**The three laws:**
1. If you haven't implemented it, you don't know it.
2. If you can't say it aloud simply, you don't understand it.
3. If you didn't beat a baseline, you didn't demonstrate anything.

```
Stage 0  Math & Programming Foundations
Stage 1  Machine Learning Core
Stage 2  Neural Networks from Scratch
Stage 3  Frameworks & the Craft of Training
Stage 4  Core Architectures (CNNs, RNNs, Attention)
Stage 5  Transformers & Large Language Models
Stage T  ── MODEL TRAINING MASTERY TRACK (parallel from here; see companion doc) ──
Stage 6  Generative Models
Stage 7  Specialized Domains
Stage 8  Scaling, Efficiency & Systems
Stage 9  The 2025–2026 Frontier
Stage 10 Trust: Interpretability, Robustness, Alignment, Uncertainty
Stage 11 Research Skills & Staying Current
```

---

# Stage 0 — Math & Programming Foundations (4–6 weeks)

You need *working fluency*, not a math degree: enough to derive backprop by hand and read a paper's methods section without panic.

### 0.1 Linear algebra
**Summary:** Deep learning is chains of matrix multiplications. A matrix is a linear transformation of space — rotation, scaling, projection. Understanding matmul as "transforming representations," dot products as similarity, and rank/SVD as "how much information a transformation preserves" gives you the geometric intuition behind embeddings, attention, and LoRA (which is literally a low-rank factorization).

🗣️ **Say it aloud:**
- What does multiplying a vector by a matrix *do*, geometrically? Why is matrix multiplication composition of transformations?
- Why is the dot product a measure of similarity? What does it mean when it's zero?
- What is the rank of a matrix in plain words? If a weight update has rank 8, what does that constrain about the update? (This *is* LoRA — you'll meet it again.)
- What does SVD decompose a matrix into, and why would keeping only the top-k singular values be a sensible compression?
- Why do we care about eigenvectors? What's special about the directions they define?

### 0.2 Calculus & the chain rule
**Summary:** Training is: compute a loss, ask "how does the loss change if I nudge each of the millions of weights," and nudge them all downhill. That question is answered by partial derivatives, and because networks are *compositions* of functions, the chain rule is the entire algorithm. The gradient is the direction of steepest ascent; its negative is where we step.

🗣️ **Say it aloud:**
- What is a gradient? Why does stepping against it decrease the loss (locally)?
- State the chain rule. Now state it for a composition of three functions. Now explain why backprop is "just" this, applied over a graph.
- What is a Jacobian, and why don't we ever materialize the full Jacobian in backprop? (Hint: vector-Jacobian products.)
- Why does a function that saturates (flat regions) cause trouble for gradient-based learning?

### 0.3 Probability & statistics
**Summary:** Models output distributions, not answers. Cross-entropy loss *is* maximum likelihood. KL divergence measures "how wrong is my distribution" and appears everywhere: VAEs, RLHF's KL penalty, distillation. If you internalize likelihood, expectation, and Bayes' rule, half of the field's loss functions become obvious rather than memorized.

🗣️ **Say it aloud:**
- What is maximum likelihood estimation in one sentence? Show that minimizing cross-entropy = maximizing likelihood for classification.
- What is KL divergence intuitively? Why is KL(P‖Q) ≠ KL(Q‖P), and give one place each direction is used.
- What is entropy of a distribution? What does a temperature parameter do to a softmax distribution, in entropy terms?
- Bayes' rule: state it, and give an example of prior → posterior updating in an ML context.
- What's the difference between the expectation of a function and the function of an expectation, and why does the difference matter (Jensen)?

### 0.4 Optimization basics
**Summary:** Loss landscapes of deep nets are wildly non-convex, yet plain-ish gradient descent works — understanding *why that's surprising* and what the failure modes are (saddle points, plateaus, poor conditioning) is the mental model behind every optimizer trick you'll learn in Stage 3.

🗣️ **Say it aloud:**
- What makes a function convex, and why is convexity nice? Why is deep learning non-convex anyway — what creates the non-convexity?
- What is a saddle point, and why are saddles more common than bad local minima in high dimensions?
- What does the learning rate trade off? Describe what training looks like when it's 10× too high and 10× too low.
- What is conditioning (ill-conditioned curvature) and how does momentum help with it?

### 0.5 Python & engineering craft
**Summary:** You will spend more hours debugging shapes and data pipelines than doing math. NumPy broadcasting, vectorized thinking, git hygiene, and using a real debugger are the difference between a 2-hour bug and a 2-day bug.

🗣️ **Say it aloud:**
- What are NumPy broadcasting rules? Given shapes (32, 1, 128) and (64, 128), what results from adding them and why?
- Why is a vectorized operation faster than a Python loop — what actually happens under the hood?
- What does `git rebase` do vs. `git merge`? When would you `git bisect`?

**Resources:** 3Blue1Brown (*Essence of Linear Algebra*, *Essence of Calculus*); *Mathematics for Machine Learning* (Deisenroth et al., free); Strang's MIT 18.06; *Python for Data Analysis* (McKinney).

**Milestone:** Linear and logistic regression from scratch in NumPy — gradients derived by hand on paper first, then coded; loss curves plotted; a README explaining every equation. No sklearn.

---

# Stage 1 — Machine Learning Core (4–6 weeks)

### 1.1 The learning paradigms
**Summary:** Supervised (labels), unsupervised (structure), **self-supervised** (labels manufactured from the data itself — the engine of the LLM era), and reinforcement (rewards from interaction). Knowing which paradigm a problem belongs to — and that most 2026 systems stack all four — is the first design decision of any project.

🗣️ **Say it aloud:**
- Define each paradigm in one sentence with one example.
- Why is next-token prediction called *self*-supervised? What's the "free label"?
- A modern chat model touches all four paradigms — name where each appears in its pipeline.

### 1.2 Generalization: bias–variance, over/underfitting
**Summary:** The single most important mental model in ML. A model that memorizes training data (high variance) fails on new data; a model too simple to capture the pattern (high bias) fails everywhere. Everything — regularization, early stopping, data augmentation, more data — is a lever on this tradeoff. Modern twist: very large networks break the classical U-curve (**double descent**), which is why "just make it bigger" surprisingly works.

🗣️ **Say it aloud:**
- Draw (in the air) train vs. validation loss for overfitting, underfitting, and healthy fit. What action does each picture demand?
- Explain bias–variance to a non-technical friend using one everyday analogy.
- What is double descent, and why does it complicate "bigger models overfit more"?
- Your model gets 99% train, 62% validation accuracy. Give three distinct hypotheses and the diagnostic for each.

### 1.3 Validation design & data leakage
**Summary:** Leakage — information from test data sneaking into training — is the #1 silent killer of real projects, and it's usually subtle: normalizing before splitting, duplicate records across splits, temporal leakage (training on the future), group leakage (same patient in train and test). A skeptical, adversarial attitude toward your own evaluation is a professional trait, not paranoia.

🗣️ **Say it aloud:**
- Name four distinct mechanisms of leakage and a concrete example of each.
- Why must preprocessing statistics (mean/std, vocabulary, feature selection) be computed on the training split only?
- When is k-fold cross-validation *wrong*? (Time series, grouped data…) What replaces it in each case?
- Your model's offline metric is great but production performance is bad. Give an ordered checklist of what you'd investigate.

### 1.4 Classical models (and when they beat deep learning)
**Summary:** Linear/logistic regression, decision trees, random forests, gradient boosting (XGBoost/LightGBM), SVMs, k-NN, k-means, PCA. Gradient boosting is *still* the thing to beat on most tabular data in 2026. These models are your baselines forever, and their failure modes teach you what deep learning actually buys you (learned representations) and what it doesn't (magic).

🗣️ **Say it aloud:**
- How does a decision tree choose splits? Why does a random forest beat a single tree — what two sources of randomness does it inject and why does averaging help?
- Explain gradient boosting as "fitting the residuals" — walk through two boosting rounds verbally.
- When would you bet on gradient boosting over a neural net, and why? (Think: data size, feature types, tabular structure.)
- What does PCA optimize? What's the connection between PCA and the SVD from Stage 0?

### 1.5 Metrics & evaluation
**Summary:** Accuracy lies on imbalanced data; a fraud model that says "never fraud" is 99.9% accurate and 100% useless. Precision/recall/F1, ROC-AUC vs PR-AUC, calibration — choosing the metric *is* choosing what the model optimizes for in the real world, and it's a product decision as much as a technical one.

🗣️ **Say it aloud:**
- Define precision and recall without notes, and give a scenario where each one is the metric that matters.
- Why does ROC-AUC look deceptively good under heavy class imbalance while PR-AUC doesn't?
- What does it mean for a model to be *calibrated*? Why might a well-calibrated 70% matter more than a higher AUC in a decision system?
- Design the evaluation metric for: (a) cancer screening, (b) spam filtering, (c) a GLOF early-warning system. Justify the asymmetries.

**Resources:** Andrew Ng's *ML Specialization*; *An Introduction to Statistical Learning* (free); StatQuest for any single concept.

**Milestone:** Full pipeline on a messy Kaggle tabular dataset: EDA → cleaning → features → 3+ models with leak-proof cross-validation → error analysis write-up explaining *why* the winner won.

---

# Stage 2 — Neural Networks from Scratch (3–4 weeks)

The stage that separates people who *use* DL from people who *understand* it.

### 2.1 The MLP and the forward pass
**Summary:** A multilayer perceptron is alternating linear transformations and pointwise nonlinearities: `h = σ(Wx + b)`, stacked. Each layer re-represents the input in a new coordinate system; depth composes simple transformations into arbitrarily complex ones (universal approximation — with caveats). Without the nonlinearity, any stack of linear layers collapses into a single linear layer, so nonlinearity is what buys expressive power.

🗣️ **Say it aloud:**
- Prove aloud that two stacked linear layers with no activation equal one linear layer.
- What does the universal approximation theorem say — and what does it *not* say (about learnability, efficiency, depth)?
- Walk through the forward pass of a 2-layer MLP on one input, naming every shape.

### 2.2 Activation functions
**Summary:** Sigmoid/tanh saturate (gradients die at extremes) — historically crippling for deep nets. ReLU's non-saturating positive half made depth trainable, at the cost of "dead" units. Modern smooth variants (GELU, SiLU/Swish) dominate transformers. The choice interacts with initialization and normalization; it's a systems decision, not aesthetics.

🗣️ **Say it aloud:**
- Why do sigmoid activations cause vanishing gradients in deep stacks? Compute (roughly) the max gradient of a sigmoid.
- What is a dead ReLU and what causes it? Two remedies?
- Why do transformers use GELU/SiLU rather than ReLU — what's the practical argument?

### 2.3 Backpropagation & automatic differentiation
**Summary:** Backprop is reverse-mode automatic differentiation: run the forward pass while recording a computational graph, then sweep backward, applying the chain rule locally at each node, accumulating gradients. Reverse mode is the right choice because we have millions of inputs (weights) and one output (loss) — one backward pass gets *all* gradients at roughly the cost of one forward pass. Deriving it fully by hand once is a rite of passage; there is no substitute.

🗣️ **Say it aloud:**
- Derive backprop for a 2-layer network with MSE loss, on an imaginary whiteboard, out loud, naming each intermediate.
- Why is reverse-mode autodiff the right mode for training (millions of params → scalar loss), and when would forward mode win?
- What does a framework store during the forward pass to make the backward pass possible, and why does that dominate GPU memory?
- What's the gradient of the loss with respect to the *input* used for? (Adversarial examples, saliency — coming in Stage 10.)

### 2.4 Loss functions & the MLE connection
**Summary:** MSE is maximum likelihood under Gaussian noise; cross-entropy is maximum likelihood for categorical outputs. Losses aren't arbitrary — they encode a probabilistic assumption about your data, and mismatched assumptions (MSE on multimodal targets, unweighted CE on imbalanced classes) produce characteristic, recognizable failures.

🗣️ **Say it aloud:**
- Derive: minimizing MSE = maximizing likelihood under what noise assumption?
- Why does MSE on a multimodal target distribution predict the (useless) mean? What family of methods fixes this? (Foreshadows generative models.)
- Why is softmax + cross-entropy numerically dangerous if implemented naively, and what's the log-sum-exp trick?

### 2.5 Initialization & gradient pathologies
**Summary:** Random init isn't arbitrary: variance must be scaled to layer width (Xavier for tanh, He for ReLU) or activations/gradients explode or vanish exponentially with depth. Understanding this teaches the deepest recurring theme in DL: **training deep networks is a battle to keep signal magnitudes stable through depth and time** — a theme that returns as normalization, residuals, and loss-spike debugging at scale.

🗣️ **Say it aloud:**
- Why does initializing all weights to zero fail completely? (Symmetry.)
- Explain He initialization's scaling factor: why √(2/fan_in) for ReLU networks?
- What happens to the forward signal in a 50-layer net whose weights are initialized 20% too large per layer? Compute the compounding aloud.

**Resources:** **Karpathy — *Neural Networks: Zero to Hero*** (build micrograd & makemore alongside him — the single best resource for this stage); Nielsen's *Neural Networks and Deep Learning*.

**Milestone:** Build a micrograd-style autograd engine (~150 lines), train an MLP on MNIST with it, then write a blog post explaining backprop to a beginner. Can't explain it → don't know it.

---

# Stage 3 — Frameworks & the Craft of Training (4–5 weeks)

> ⚠️ This stage is the foundation of the **Model Training Mastery track** ([companion doc](./MODEL_TRAINING_MASTERY.md)). Everything here recurs at 1000× scale there.

### 3.1 PyTorch fluency
**Summary:** PyTorch is the field's lingua franca: tensors, autograd, `nn.Module`, `Dataset`/`DataLoader`, device management, `torch.compile`. Fluency means you can write a custom training loop, a custom layer, and a custom loss in minutes without documentation — the framework disappears and only the ideas remain. (JAX exists — functional, research/Google world; learn later if needed.)

🗣️ **Say it aloud:**
- What does `loss.backward()` actually do? Why must you call `optimizer.zero_grad()` — what happens if you don't, and when is that behavior actually *useful*? (Gradient accumulation.)
- What's the difference between `model.eval()` and `torch.no_grad()`? Name a bug caused by forgetting each.
- Why is data loading often the real bottleneck, and what do `num_workers`, prefetching, and pinned memory do about it?

### 3.2 Optimizers
**Summary:** SGD follows the raw gradient; momentum smooths it over steps; Adam/AdamW additionally normalize per-parameter by a running estimate of gradient magnitude, making learning rates transferable across layers. AdamW (decoupled weight decay) is the 2026 default. Newer optimizers matter at scale: **Muon** (used in several 2025–26 frontier runs), Lion, Sophia, Shampoo/SOAP — know what problem each claims to solve (mostly: better-conditioned updates, less memory, or faster convergence per FLOP).

🗣️ **Say it aloud:**
- Explain Adam's two moment estimates and what each does. Why does it need bias correction early in training?
- What's the difference between L2 regularization and decoupled weight decay (the W in AdamW), and why did coupling them inside Adam misbehave?
- Why does Adam use ~2× extra memory per parameter, and why does that matter enormously for LLM fine-tuning? (Foreshadows QLoRA's paged optimizers.)
- When does plain SGD+momentum still beat Adam? (Vision, generalization gap arguments.)

### 3.3 Learning-rate schedules
**Summary:** LR is the single most important hyperparameter. Warmup (start tiny, ramp up) prevents early instability while Adam's statistics are unreliable; cosine decay (or warmup-stable-decay) anneals to fine-grained convergence. The batch-size ↔ LR relationship (bigger batch → higher LR, up to a noise-dependent ceiling) is core large-scale training knowledge.

🗣️ **Say it aloud:**
- Why does warmup exist? What specifically goes wrong in Adam's first ~100 steps without it?
- Sketch (in the air) a warmup + cosine schedule, and explain what each region does for optimization.
- If you double the batch size, what should you do to the LR and why? Where does that scaling break down?

### 3.4 Normalization
**Summary:** Normalization layers re-center and re-scale activations so each layer receives inputs at stable magnitude, easing optimization dramatically. BatchNorm (statistics across the batch — great for CNNs, breaks for variable-length sequences and small batches), LayerNorm (across features, per token — the transformer standard), RMSNorm (LayerNorm minus mean-centering — cheaper, now the LLM default). Placement (pre-norm vs post-norm) decides whether 100-layer transformers train at all.

🗣️ **Say it aloud:**
- What axes do BatchNorm and LayerNorm normalize over? Why is BatchNorm wrong for autoregressive language models (two reasons)?
- Why does BatchNorm behave differently at train vs. eval time, and what classic bug does this cause?
- What is pre-norm vs post-norm placement in a transformer block, and why did the field converge on pre-norm?

### 3.5 Regularization & augmentation
**Summary:** Dropout (random unit deletion → implicit ensembling), weight decay, label smoothing, early stopping, and — often most powerful of all — **data augmentation**, which encodes invariances you know the task has (a rotated cat is a cat). Mixup/CutMix blend training examples for smoother decision boundaries. In the LLM era, "more diverse data" has largely replaced explicit regularization, which itself is a lesson.

🗣️ **Say it aloud:**
- Why does dropout at inference time need scaling (or inverted dropout at train time)? What ensemble is dropout secretly approximating?
- What invariances does augmentation encode? Give an augmentation that would be *harmful* for digit classification. (Vertical flip: 6→9.)
- Why is heavy explicit regularization less prominent in LLM pretraining than in small-data vision?

### 3.6 The training debugging loop
**Summary:** Professional training is a diagnostic discipline. The canon: **overfit a single batch first** (if you can't, the pipeline is broken — no point training); watch gradient norms; know the loss-curve pathologies by sight (spike = LR/data issue; plateau-then-drop = LR too high then schedule kicked in; train↓ val↑ = overfitting; loss = ln(num_classes) = predicting uniform, check labels/wiring). This skill compounds forever.

🗣️ **Say it aloud:**
- Why is overfitting one batch the universal first sanity check? What failure classes does it rule out vs. not rule out?
- Your CE loss on a 10-class problem sits exactly at 2.303 and doesn't move. What is the model doing, and what are your first three checks?
- Loss suddenly spikes at step 40k after healthy progress. List your hypotheses in the order you'd test them. (Bad data shard, LR too high for current loss landscape, numerical issue, …)
- Gradient norm is 100× larger in layer 1 than layer 30. Healthy or pathological? What would you look at?

### 3.7 Mixed precision, memory & gradient mechanics
**Summary:** Modern training runs in bf16/fp16 with fp32 master weights (and fp8 at the frontier): ~2× memory and throughput wins, with numerical care required (loss scaling for fp16; bf16 mostly avoids it via wider exponent range). Gradient **accumulation** simulates big batches on small GPUs; gradient **clipping** caps update magnitude to survive rare huge gradients. Know the GPU memory budget by heart: weights + gradients + optimizer states + activations.

🗣️ **Say it aloud:**
- fp16 vs bf16: same bits, different split — which has more range, which more precision, and why did bf16 win for training?
- For a 7B-parameter model trained with AdamW in mixed precision, roughly how many bytes per parameter do weights + grads + optimizer states cost? (Walk the arithmetic aloud — this is interview canon: ~16 bytes/param before activations.)
- What exactly does gradient accumulation compute, and what must you divide by to keep the effective loss consistent?
- What does gradient clipping protect against, and what does habitually-active clipping tell you about your run?

### 3.8 Experiment discipline
**Summary:** Track everything (W&B/MLflow), config-as-code, seeds and determinism, one-change-at-a-time ablations. The uncomfortable truth: most "improvements" people report are noise; the pros distinguish signal via repeated runs and honest baselines. Reproducibility is a professional ethic, and it is what makes your later ablation tables believable.

🗣️ **Say it aloud:**
- Your new trick improves accuracy by 0.4%. What do you need before believing it? (Multiple seeds, variance estimate, unchanged baseline.)
- Why can two runs with identical seeds still differ on GPU? (Non-deterministic kernels, atomics.)
- What belongs in an experiment config for it to be reproducible in 6 months?

**Resources:** Official PyTorch tutorials; **Karpathy — *A Recipe for Training Neural Networks*** (read three times, it's the syllabus for 3.6); fast.ai for the top-down complement.

**Milestone:** CIFAR-10 to **>94%** with a from-scratch loop: augmentation, schedule, W&B logging, and an ablation table quantifying each trick's contribution across ≥2 seeds.

---

# Stage 4 — Core Architectures (5–6 weeks)

### 4.1 Convolutions & the vision stack
**Summary:** A convolution slides small learned filters across an image: local connectivity + weight sharing = built-in translation equivariance and vastly fewer parameters than an MLP on pixels. Stacked, filters compose into a hierarchy (edges → textures → parts → objects). Receptive field — how much input a deep unit "sees" — is the key design quantity. This is the canonical example of an **inductive bias**: architecture encoding assumptions about data.

🗣️ **Say it aloud:**
- Compute aloud: 224×224×3 input, 3×3 conv, 64 output channels — how many parameters? Versus a dense layer to 64 units?
- What is weight sharing buying you, statistically? What assumption about images does it encode?
- How do stride, dilation, and depth each grow the receptive field?
- What is an inductive bias? Contrast the conv bias with the transformer's (weaker) bias, and explain the data-scale implications — why do ViTs need more data or heavier augmentation?

### 4.2 The architecture arc & residual connections
**Summary:** LeNet → AlexNet (GPUs + ReLU + scale) → VGG (uniform depth) → **ResNet**: the genuinely important idea. Skip connections let layers learn *residuals* (deviations from identity), creating gradient highways that made 100+ layer networks trainable. Residual streams are now everywhere — every transformer is a residual network. ConvNeXt (modernized CNNs) shows the conv/transformer gap was mostly training recipe, another lesson: **recipes matter as much as architectures**.

🗣️ **Say it aloud:**
- Explain the degradation problem ResNet solved — why did *deeper* nets get *worse train* error (not just test)?
- Why do skip connections help gradients? Trace the gradient path through a residual block aloud.
- "A transformer is a residual stream that layers read from and write to" — unpack this sentence. (It's also the framing mechanistic interpretability uses — Stage 10.)

### 4.3 Transfer learning & fine-tuning (vision edition)
**Summary:** Features learned on large datasets transfer: take a pretrained backbone, replace the head, fine-tune. Decisions: freeze vs. full fine-tune, layer-wise LR decay (early layers = generic features, lower LR), when linear probing suffices. This is 95% of practical vision work — and the conceptual warm-up for the entire Model Training Mastery track.

🗣️ **Say it aloud:**
- Why do early conv layers transfer across almost any visual task while late layers don't?
- You have 500 labeled images. Full fine-tune, partial freeze, or linear probe — how do you decide, and what would you measure?
- What is catastrophic forgetting, and why does a lower LR (or freezing) mitigate it? (You will meet this at LLM scale in the training track.)

### 4.4 Detection & segmentation
**Summary:** Beyond "what": **detection** (what + where — YOLO's single-shot regression; DETR's set-prediction-with-transformers), **semantic segmentation** (per-pixel classes — U-Net's encoder-decoder with skip connections is the workhorse, ubiquitous in medical/satellite work), **instance segmentation** (Mask R-CNN), and **promptable segmentation** (SAM/SAM-2 — a segmentation foundation model). These are where vision earns money.

🗣️ **Say it aloud:**
- Why is detection harder than classification — what makes "a variable number of outputs" architecturally awkward, and how do YOLO vs. DETR each resolve it?
- Draw U-Net in the air. Why do the skip connections carry exactly what the decoder lacks?
- What does IoU measure, and what does non-maximum suppression clean up?
- What makes SAM a "foundation model" for segmentation rather than just a big segmenter?

### 4.5 Recurrent networks
**Summary:** RNNs process sequences by threading a hidden state through time — elegant, but the same weights multiplied T times means exponentially vanishing/exploding gradients, and step-by-step processing can't parallelize across the sequence. LSTMs/GRUs add gates (learned "remember/forget" valves) that fix gradient flow but not the parallelism. Understand them well: they explain *why* transformers won, and their core idea — constant-size state summarizing history — is reborn in 2026's state space models (Mamba).

🗣️ **Say it aloud:**
- Why do vanilla RNN gradients vanish/explode over long sequences? Connect it to repeated multiplication by the recurrent weight matrix.
- What do the LSTM's gates do, mechanically? Which design element protects the gradient (the additive cell-state path)?
- Name the two independent reasons transformers displaced RNNs (parallelism; direct long-range access) — and the RNN property that Mamba-class models resurrect and why (O(1) state per step at inference).

### 4.6 Attention (the original idea) & embeddings
**Summary:** In seq2seq translation, forcing a whole sentence through one fixed vector was the bottleneck; Bahdanau attention let the decoder look back at *all* encoder states, weighting them by learned relevance — attention as **content-based, differentiable soft lookup**. Separately, word2vec showed words can be embedded in vector space where geometry = meaning, and contrastive learning (SimCLR, **CLIP**) generalized this: pull matching pairs together, push others apart — the trick behind image-text alignment powering all multimodal AI.

🗣️ **Say it aloud:**
- Explain Bahdanau attention as a soft dictionary lookup: what plays query, key, value?
- Why "soft" (weighted average) rather than "hard" (pick one)? What does differentiability buy?
- How does word2vec turn raw text into supervision? Why does "similar contexts → nearby vectors" fall out?
- Explain CLIP's training objective aloud, and why it enables zero-shot classification.

**Resources:** Stanford **CS231n** (do the assignments); *Dive into Deep Learning* (d2l.ai); distill.pub archive.

**Milestone:** (1) Fine-tune a pretrained ConvNeXt/ResNet on ~1–2k images you collect yourself, deploy behind a simple API; (2) build a character-level LSTM language model from scratch and sample from it — you'll feel exactly why attention was needed.

---

# Stage 5 — Transformers & Large Language Models (6–8 weeks)

The center of gravity of the field. Go deep. **From this stage onward, run the [Model Training Mastery track](./MODEL_TRAINING_MASTERY.md) in parallel** — it drills every training concept below to mastery depth.

### 5.1 Self-attention & multi-head attention
**Summary:** Every token emits a query ("what am I looking for"), a key ("what I contain"), and a value ("what I'll contribute"). Attention weights = softmax(QKᵀ/√d): each token gathers a relevance-weighted mixture of all tokens' values, in parallel, with direct connections between any pair regardless of distance. Multiple heads run this in parallel subspaces so different heads can track different relations (syntax, coreference, position). This one mechanism is the engine of the modern era — over-invest here.

🗣️ **Say it aloud:**
- Walk through scaled dot-product attention shape by shape, from (batch, seq, d_model) to output, aloud, no notes.
- Why divide by √d_k? What happens to softmax gradients if you don't?
- What is the causal mask, mechanically, and why does it make training on all positions *simultaneously* possible? (This parallel-training trick is why the whole paradigm scales.)
- Why is attention O(n²) in sequence length, and which part (compute or memory) hurts first in practice?
- What would a two-head toy example let you represent that one head can't?

### 5.2 Positional encodings
**Summary:** Attention is permutation-invariant — a bag of tokens — so position must be injected. Arc: sinusoidal (fixed) → learned absolute → **RoPE** (rotary: rotate Q/K by position-dependent angles so attention depends on *relative* position — the 2026 standard) → ALiBi (distance-penalty biases). Positional encoding choice determines **length extrapolation**: whether a model trained at 8k context can work at 128k. RoPE scaling tricks (PI, NTK-aware, YaRN) are how long-context models are made — drilled hands-on in the training track.

🗣️ **Say it aloud:**
- Prove aloud that self-attention without positional information is permutation-equivariant.
- What does RoPE do to queries and keys, and why does the dot product of two rotated vectors depend only on relative position?
- Why do absolute learned positions fail beyond training length, and what's the intuition for why RoPE + interpolation extends context?

### 5.3 The transformer block & the three architectures
**Summary:** A block = attention (token mixing) + MLP (per-token processing, holding most parameters and, per interpretability research, most stored knowledge) + residual connections + pre-norm. Stack N blocks on a residual stream. Three arrangements: encoder-only (BERT — bidirectional, understanding tasks), decoder-only (GPT — causal, generation; **the dominant paradigm**), encoder-decoder (T5 — conditioned generation). Decoder-only won on simplicity and unified in-context learning.

🗣️ **Say it aloud:**
- Sketch the full pre-norm block aloud: input → ? → ? → output. Where exactly do the two residual additions happen?
- What's the parameter count split between attention and MLP in a standard block (MLP ratio 4×)? Walk the arithmetic for d_model=4096.
- Why did decoder-only win over encoder-decoder for general-purpose models? What can BERT do that GPT structurally can't (and vice versa)?
- "The residual stream is a shared memory that attention and MLPs read from and write to." Defend this framing.

### 5.4 Tokenization
**Summary:** Models see integer IDs from a learned subword vocabulary (BPE: iteratively merge frequent pairs; or Unigram/SentencePiece). Tokenization causes real, weird failures — arithmetic (digits split inconsistently), spelling tasks, and brutal inefficiency on underrepresented languages (3–5× more tokens per sentence = less effective context, worse learning, higher cost). **Fertility** (tokens per word) is the metric. This topic is the gateway to vocabulary transplants in the training track and the second problem statement.

🗣️ **Say it aloud:**
- Run BPE by hand aloud on a toy corpus for three merges.
- Why do LLMs struggle to count letters in a word? Trace the failure to tokenization.
- Why is a tokenizer trained on English text a *tax* on Hindi or Konkani users? Quantify what 4× fertility does to effective context length and per-token pricing.
- What is byte fallback and what failure does it prevent?

### 5.5 Pretraining & data curation
**Summary:** Pretraining = next-token prediction over trillions of tokens. The 2024–26 consensus: **data quality/mixture beats raw quantity** — dedup (MinHash), quality filtering (classifier-scored), domain mixing ratios, multi-epoch tradeoffs, and data curriculum are where frontier labs pour effort. Loss on held-out text follows smooth **scaling laws**; Chinchilla established compute-optimal token/parameter ratios (~20:1), but deployment economics pushed "overtraining" small models far past that (Llama-style), because inference cost dominates. Full drill-down in the training track.

🗣️ **Say it aloud:**
- Why does the same document appearing 100 times in the corpus hurt? Two distinct mechanisms (memorization, wasted compute).
- State Chinchilla's finding in one sentence. Then explain why Llama-class models deliberately violate it and why that's rational.
- What does a "quality classifier" for pretraining data do, and what's the circularity risk in using an LLM to filter LLM training data?
- Why is benchmark contamination a data-curation problem, and how would you detect it?

### 5.6 Supervised fine-tuning (SFT) & instruction following
**Summary:** A pretrained model is a text-completer, not an assistant. SFT on (instruction → response) pairs teaches the *format and behavior* of helpfulness; chat templates (system/user/assistant tokens) structure the dialogue; loss is masked so the model learns to produce responses, not to predict user turns. Key insight ("superficial alignment hypothesis"): capabilities come from pretraining; SFT mostly *elicits* and *styles* them — which is why a few thousand excellent examples (LIMA-style) can beat a million mediocre ones.

🗣️ **Say it aloud:**
- Why does loss masking on the prompt matter in SFT? What subtle behavior shift happens if you train on user turns too?
- Base model vs. instruct model: give three behavioral differences you could demonstrate in five minutes.
- Argue both sides: "SFT teaches new knowledge" vs. "SFT teaches format." What experiment discriminates the hypotheses?

### 5.7 Preference alignment: RLHF → DPO → GRPO
**Summary:** SFT can't express "response A is *better* than B." Preference alignment can: classic **RLHF** trains a reward model on human preference pairs, then optimizes the policy with PPO under a KL penalty (stay close to the SFT model). **DPO** collapses this into a single supervised loss directly on preference pairs — simpler, no reward model, no rollouts. **GRPO** (the DeepSeek-R1 method) drops the value network and normalizes rewards within groups of samples, powering **RLVR** — RL from *verifiable* rewards (did the math check? did tests pass?) — which is the engine of 2025–26 reasoning models. Full mechanics in the training track.

🗣️ **Say it aloud:**
- Why can't plain SFT capture preference information? What exactly does a reward model learn?
- What does the KL penalty in RLHF prevent? Describe what a policy that "hacks" its reward model looks like.
- Explain DPO's core trick in one sentence: what does it treat as an implicit reward?
- What makes a reward "verifiable," and why did verifiable rewards break the reward-hacking ceiling and enable reasoning training?
- What is sycophancy, and why does optimizing against human *approval* produce it?

### 5.8 Parameter-efficient fine-tuning (LoRA & friends)
**Summary:** Full fine-tuning of a 70B model needs ~1.1TB of optimizer state. **LoRA**: freeze weights, learn low-rank updates ΔW = BA (rank r ≪ d) on attention/MLP projections — <1% trainable parameters, near-full-FT quality on most tasks, and the update merges back into W at zero inference cost. **QLoRA** trains LoRA atop a 4-bit-quantized frozen base (NF4, double quantization, paged optimizers) — a 70B fine-tune on one workstation. This is how everyone without a datacenter customizes models; mastery-depth coverage in the training track.

🗣️ **Say it aloud:**
- Walk the LoRA parameter math aloud: d=4096, r=16, one weight matrix — how many trainable params vs. full?
- Why is low-rank a plausible prior for *fine-tuning* updates specifically (task adaptation ≈ small subspace) when it would be terrible for pretraining?
- What do rank r and scaling α control? What actually happens when you merge the adapter?
- In QLoRA, which numbers are 4-bit and which are bf16 during a training step? Trace one forward-backward pass aloud.

### 5.9 Mixture-of-Experts (MoE)
**Summary:** Replace each MLP with N expert MLPs plus a learned router that sends each token to its top-k experts: total parameters grow enormously, per-token compute stays modest. Nearly every 2025–26 frontier model is MoE (DeepSeek-V3's 671B-total/37B-active is the canonical open example). Costs: router load-balancing (auxiliary losses to prevent expert collapse), memory (all experts resident), infrastructure complexity. MoE = the decoupling of *knowledge capacity* from *inference cost*.

🗣️ **Say it aloud:**
- Explain "sparse activation": how can a 671B model cost ~37B per token? Where does the 37B figure come from?
- What is expert collapse, why does the naive router cause it, and what do load-balancing losses do?
- What does MoE decouple? Why is that the economically decisive property?
- What's the memory catch — why isn't MoE free even though FLOPs are low?

### 5.10 Multimodality & vision-language models
**Summary:** **ViT** treats images as sequences of patch tokens — transformers eat pixels. **CLIP** aligns image and text embeddings contrastively. **VLMs** (LLaVA lineage) bolt a vision encoder onto an LLM via a projector, treating image features as soft tokens. 2026 frontier models are **natively multimodal** ("omni"): text, image, audio, video in; multiple modalities out; trained jointly from early on. The unifying idea: *everything becomes tokens in a shared sequence*.

🗣️ **Say it aloud:**
- How does ViT turn a 224×224 image into a token sequence? How many tokens for 16×16 patches?
- In a LLaVA-style VLM, what exactly does the projector map between? Why can a frozen LLM "understand" projected image features at all?
- Adapter-style VLM vs. natively multimodal training: what does each buy?

### 5.11 Inference mechanics
**Summary:** Autoregressive generation is one-token-at-a-time; naive recomputation would be O(n²) per token, so the **KV cache** stores past keys/values — making inference *memory-bandwidth-bound* and making cache size (layers × heads × context × d) the real constraint on context length. **GQA** (share KV heads across query heads) shrinks the cache; sampling knobs (temperature, top-p, repetition penalties) shape the output distribution. This is why long context is expensive and why Stage 8's serving tricks exist.

🗣️ **Say it aloud:**
- What exactly is stored in the KV cache and why never the queries?
- Compute aloud the KV-cache size for a 32-layer, 8-KV-head, d_head=128 model at 32k context in bf16.
- Why is decoding memory-bound while prefill is compute-bound? What does that asymmetry imply for serving?
- What do temperature and top-p each do to the sampling distribution? When is greedy decoding the wrong choice even for "factual" tasks?

### 5.12 Using LLMs: RAG, agents, evals
**Summary:** The applied layer. **RAG**: embed a corpus, retrieve relevant chunks, stuff them in context — grounding generation in your data; the craft is chunking, hybrid retrieval, reranking, and knowing when 1M-token contexts make RAG unnecessary (they don't, for large/fresh corpora — but the boundary moved). **Agents**: LLMs in tool-use loops (reason → act → observe), with planning, memory, and **MCP** as the standard tool-integration protocol; reliability engineering is the hard part. **Evals**: benchmarks are contaminated and saturating; the employable skill is building *your own* task-specific eval harness, including LLM-as-judge with known biases (position, length, self-preference).

🗣️ **Say it aloud:**
- Walk through a RAG pipeline component by component, naming what goes wrong at each stage (bad chunking, embedding mismatch, lost-in-the-middle…).
- When does long context beat RAG and when the reverse? Name three factors (corpus size, freshness, cost/latency).
- What is the ReAct loop? Why do agent error rates *compound*, and what does that imply for tool design?
- Name three known biases of LLM-as-judge and a mitigation for each.
- Why is "we improved on MMLU" weak evidence in 2026? What makes a private eval trustworthy?

**Resources:** **Karpathy: "Let's build GPT" + nanoGPT ("Let's reproduce GPT-2")** — non-negotiable; *The Annotated Transformer*; Stanford **CS224n** and **CS336** (build-an-LLM-from-scratch); HF courses; papers: *Attention Is All You Need*, GPT-2/3, LLaMA series, Chinchilla, InstructGPT, DPO, **DeepSeek-V3 + R1 reports** (best public documentation of frontier training).

**Milestone:** (1) Train a nanoGPT-scale model (~10–100M params) from scratch on a corpus you choose; (2) QLoRA-fine-tune an open model on a task you care about, DPO-align it on a small preference set, and build an eval harness proving the fine-tune beats the base. *(These double as Gauntlet challenges G2/G4/G9 in the training track.)*

---

# Stage 6 — Generative Models (4–6 weeks)

### 6.1 Autoencoders & VAEs
**Summary:** Autoencoders compress-then-reconstruct, learning latent representations. **VAEs** make the latent space probabilistic: encode to a distribution, sample (via the reparameterization trick, which keeps sampling differentiable), decode; the ELBO loss = reconstruction + KL regularization toward a prior, yielding a smooth, sampleable latent space. VAEs' samples are blurry (Gaussian likelihood → averaging), but the latent-space machinery is load-bearing: **latent diffusion runs inside a VAE**.

🗣️ **Say it aloud:**
- Why can't you backprop through sampling naively, and how exactly does reparameterization fix it?
- What do the two ELBO terms trade off? What happens if the KL term dominates (posterior collapse)?
- Why are VAE images blurry — connect it to the MSE/multimodality point from Stage 2.4.

### 6.2 GANs
**Summary:** Generator forges, discriminator detects, both improve adversarially — sharp samples, no explicit likelihood, notoriously unstable (mode collapse, oscillation). Largely superseded by diffusion for images, but know them: the *adversarial idea* recurs (GAN losses inside distillation, adversarial robustness), and StyleGAN's disentangled latent space remains a landmark.

🗣️ **Say it aloud:**
- Describe the minimax game and why its equilibrium (in theory) matches the data distribution.
- What is mode collapse, in one sentence, and why does the vanilla objective invite it?
- Where does adversarial training survive in the 2026 stack even though "GANs are dead"?

### 6.3 Diffusion models
**Summary:** The dominant continuous-generation paradigm. Forward: gradually noise data to pure Gaussian. Learn: a network (typically predicting the noise ε, conditioned on timestep) that reverses one step. Generate: start from noise, denoise iteratively. Equivalent score-based view: the model learns ∇ log p(x) and follows it. Key practical stack: **latent diffusion** (diffuse in a VAE's latent space — Stable Diffusion's trick, ~50× cheaper), **classifier-free guidance** (train conditional+unconditional jointly, extrapolate between them at sampling for prompt adherence), ControlNet-style conditioning, and **DiT** (transformer backbones — the architecture behind Sora-class video).

🗣️ **Say it aloud:**
- Why is *reversing small noise steps* learnable when *generating from scratch in one step* isn't? (What does each denoising step actually have to predict?)
- What does the network take in and put out in a standard DDPM? Why predict ε rather than x₀ directly (variance argument)?
- Explain classifier-free guidance mechanically: what two predictions are combined, and what does the guidance scale trade off?
- Why does latent diffusion change the economics? What role does the VAE play at train vs. sample time?
- Diffusion vs. autoregression: contrast the factorization of the joint distribution each one uses.

### 6.4 Flow matching & few-step generation
**Summary:** **Flow matching / rectified flow** — the cleaner successor to diffusion training: learn a velocity field transporting noise to data along (ideally straight) paths; simpler objective, straighter trajectories, fewer sampling steps; the backbone of current frontier image models (Flux, SD3-class). **Consistency models / distillation** compress 50-step samplers into 1–4 steps for real-time generation. Direction of travel: diffusion and flow matching as two views of one continuous-time framework.

🗣️ **Say it aloud:**
- What does the flow-matching network predict, and how does sampling become an ODE solve?
- Why do straighter probability paths mean fewer sampling steps?
- What does a consistency model enforce between points on the same trajectory, and why does that enable one-step generation?

### 6.5 Discrete generation: AR images/audio, neural codecs
**Summary:** The other route: tokenize continuous signals with a **VQ-VAE / neural codec** (learn a discrete codebook), then autoregress over tokens with a transformer — the approach behind speech models and some image models, and the reason "omni" models can emit audio: everything becomes tokens. Whisper-class ASR and modern TTS live here.

🗣️ **Say it aloud:**
- What does vector quantization do to a continuous latent, and how does the codebook get learned despite argmax being non-differentiable (straight-through)?
- Why does tokenizing audio let you reuse the entire LLM stack on speech?
- Trade off AR-over-tokens vs. diffusion for images: fidelity, speed, controllability, unification with text.

### 6.6 Video generation & evaluation of generative models
**Summary:** Video generation (DiT over spatiotemporal latent patches) exploded 2024–26; the hard parts are temporal consistency, physics plausibility, and cost — and its convergence with **world models** (Stage 9.3) is the deepest storyline: a good video generator implicitly models how the world evolves. Evaluation of any generative model is unsolved-ish: FID's Gaussian assumptions creak, human eval is noisy and expensive, and precision (fidelity) vs. recall (coverage) must be separated.

🗣️ **Say it aloud:**
- Why is temporal consistency fundamentally harder than per-frame quality?
- What two things can be traded off when a generator has high precision but low recall? Which failure does mode collapse correspond to?
- Why might a model with *better* FID produce *worse-looking* images? What does that teach about proxy metrics?

**Resources:** Lilian Weng — *What are Diffusion Models?* (and the whole blog); *Understanding Deep Learning* (Prince, free — superb on generative models); HF Diffusers course; papers: DDPM, Latent Diffusion, DiT, Flow Matching (Lipman et al.).

**Milestone:** DDPM from scratch on MNIST/CIFAR → add class-conditioning with classifier-free guidance → then LoRA/DreamBooth-fine-tune a Stable-Diffusion-class model on your own concept *(doubles as Gauntlet G11)*.

---

# Stage 7 — Specialized Domains (pick 2–3 · 4–8 weeks)

Each is a career-sized rabbit hole; summaries + one probe question each. Choose by where you want to work.

- **Graph Neural Networks.** Message passing: nodes update by aggregating neighbors; GCN/GAT/GraphSAGE, graph transformers; molecules, recommenders, traffic, knowledge graphs. Watch for over-smoothing (deep GNNs make all nodes identical). *(PyTorch Geometric; Stanford CS224W.)* — 🗣️ *Why must the neighbor-aggregation function be permutation-invariant, and what does that restrict?*
- **Deep RL.** MDPs, Q-learning → DQN, policy gradients → PPO, actor-critic, offline RL, model-based RL. In 2026 RL matters most as (a) the engine of reasoning training (GRPO/RLVR — training track §9) and (b) robotics. *(Spinning Up; David Silver; CleanRL.)* — 🗣️ *Explain the deadly triad (function approximation + bootstrapping + off-policy) and why it destabilizes learning.*
- **AI for Science.** AlphaFold-class structure prediction; **PINNs** (physics equations as loss terms); **neural operators** (FNO — learn PDE solution operators, 1000× faster than solvers); ML weather (GraphCast/GenCast now beating traditional NWP); materials (GNoME). Highest-impact direction of the decade. — 🗣️ *What does a neural operator learn that a normal net doesn't (function→function vs point→point), and why does that matter for changing resolutions?*
- **Time series.** Respect classical baselines (ARIMA, ETS — genuinely hard to beat); N-HiTS, PatchTST; **TS foundation models** (TimesFM/Chronos-class zero-shot forecasters). — 🗣️ *Why does naive backtesting leak, and what does a proper rolling-origin evaluation look like?*
- **Audio & speech.** Whisper-class ASR, neural TTS, codecs, real-time voice-to-voice. — 🗣️ *Why did TTS move from spectrogram+vocoder pipelines to token-based LM approaches?*
- **Embodied AI / robotics.** **VLA models** (RT-2, π0/OpenVLA lineage), imitation learning, **diffusion policies**, sim-to-real. Arguably the hottest 2026 frontier. — 🗣️ *Why is a diffusion policy a natural fit for multimodal action distributions where regression fails?*
- **Geospatial / remote sensing.** Sentinel-1/2 imagery, SAR, geospatial foundation models (Prithvi/Clay lineage). Directly feeds [the GLOF problem](./PROBLEM_STATEMENT.md). — 🗣️ *Why does self-supervised pretraining matter more in satellite imagery than almost any other domain? (Label scarcity + unlabeled abundance.)*

**Milestone:** One substantial project in a chosen domain using its native architectures, benchmarked against that domain's classical baseline.

---

# Stage 8 — Scaling, Efficiency & Systems (4–6 weeks)

What separates hobbyists from people who ship — and increasingly *the* hiring differentiator.

### 8.1 The GPU mental model
**Summary:** GPUs have enormous FLOPs but comparatively slow memory; the ratio (arithmetic intensity) decides whether a kernel is **compute-bound** (big matmuls) or **memory-bound** (elementwise ops, attention at long context, decoding). The roofline model makes this one picture. This single concept explains FlashAttention, KV caches, quantization wins, and why "fewer FLOPs" often isn't faster. Read Horace He's *Making Deep Learning Go Brrrr*.

🗣️ **Say it aloud:**
- Define arithmetic intensity. Place matmul, LayerNorm, and single-token decoding on the roofline, aloud.
- Why is LLM decoding memory-bandwidth-bound? Derive it: how many bytes move per token generated vs. FLOPs done?
- What did FlashAttention actually change — FLOPs or memory traffic? Explain tiling + recomputation in two sentences.

### 8.2 Distributed training
**Summary:** One GPU fits nothing interesting. **DDP** (replicate model, shard data, all-reduce gradients); **ZeRO/FSDP** (shard optimizer states/gradients/parameters — the biggest memory lever); **tensor parallelism** (split individual matmuls — needs fast interconnect); **pipeline parallelism** (split layers into stages — mind the bubbles); context parallelism for extreme sequence lengths. Frontier training composes all of them ("3D parallelism"). Hands-on drill in the training track §11.

🗣️ **Say it aloud:**
- Walk the memory math: why does DDP on a 7B model with AdamW blow a 24GB card even at batch size 1, and what exactly does each ZeRO stage shard?
- Why does tensor parallelism demand NVLink-class interconnect while data parallelism tolerates Ethernet?
- What is a pipeline bubble and how do microbatches shrink it?
- You have 8 GPUs and a model that fits on one: which parallelism? A model 4× too big for one: what combination?

### 8.3 Inference optimization & serving
**Summary:** Serving economics: **PagedAttention/vLLM** (virtual-memory-style KV-cache management → high GPU utilization), **continuous batching** (don't wait for the slowest sequence), **speculative decoding** (small draft model proposes, big model verifies in parallel — exact same distribution, 2–3× faster), prefix caching (shared system prompts). Latency splits into TTFT (prefill) and TPOT (decode) — optimize them separately.

🗣️ **Say it aloud:**
- What memory-management problem does PagedAttention solve, and what's the OS analogy?
- Why is speculative decoding *lossless* — what exactly does the verify step guarantee?
- Why does continuous batching raise throughput so much over static batching?

### 8.4 Compression: quantization, distillation, pruning
**Summary:** **Quantization** (int8 → 4-bit GPTQ/AWQ/NF4; FP8/FP4 now in *training* at the frontier) shrinks memory and, because inference is memory-bound, speeds it up — usually with tiny quality loss (watch outlier channels). **Distillation** — training small models on big models' outputs — is how 2026's small models punch at last year's frontier weight. **Pruning + healing** removes structure then retrains. Hands-on in the training track §8.

🗣️ **Say it aloud:**
- Why does weight-only 4-bit quantization speed up *decoding* even though compute still runs in bf16?
- What are activation outliers and why do they make naive int8 fail on large LLMs?
- Sequence-level distillation vs logit distillation: what does each transfer, and when do you need the teacher's logits?

### 8.5 Edge & deployment + MLOps
**Summary:** ONNX/TensorRT, llama.cpp/GGUF, ExecuTorch — running models on phones and Raspberry Pis is its own craft (operator support, memory maps, thermal limits). Around it all sits **MLOps**: data versioning, CI for models, monitoring & drift detection, shadow deployments, rollback plans — the unglamorous 80% of real ML work, and where projects die.

🗣️ **Say it aloud:**
- What breaks first when you move a model from server GPU to phone? (Memory, ops, precision, thermals — order them.)
- Design aloud a shadow deployment for a new model version: what do you compare, for how long, with what rollback trigger?
- What is data drift vs concept drift, and one detector for each?

### 8.6 Cost math
**Summary:** Pros estimate before they train: training FLOPs ≈ 6·N·D (parameters × tokens), GPU-hours from achieved MFU, inference cost per million tokens from bandwidth math. Fermi-estimation fluency here changes what projects you even consider — and is startlingly rare, hence valuable.

🗣️ **Say it aloud:**
- Derive the 6ND rule (2 FLOPs/param forward MAC, ×3 for backward) and estimate GPU-hours to train a 1B model on 20B tokens at 40% MFU on an A100.
- Estimate the cost of serving 1M requests/day of 500 tokens each on rented H100s. Walk every assumption aloud.

**Resources:** HF *Ultra-Scale Playbook*; vLLM & FlashAttention papers; Chip Huyen — *Designing ML Systems* + *AI Engineering*.

**Milestone:** Quantize your Stage-5 fine-tune to 4-bit, serve with vLLM, benchmark latency/throughput/quality vs fp16, write the tradeoff table. Bonus: FSDP multi-GPU run of your nanoGPT *(Gauntlet G12)*.

---

# Stage 9 — The 2025–2026 Frontier (ongoing)

Engage seriously once Stages 5–8 are solid. Each theme: summary + the questions that test whether you understand it *beyond the hype*.

### 9.1 Reasoning models & test-time compute — *the defining shift*
**Summary:** Models now "think before answering": long chains of thought trained via **RL on verifiable rewards** (math/code correctness) — the o1/o3 → DeepSeek-R1 → 2026-default lineage. The scaling frontier moved from pretraining compute to **inference-time compute**: longer thinking, best-of-N with verifiers, search. Complications: process vs outcome rewards, CoT (un)faithfulness — the visible reasoning is not always the real reasoning — and distilling reasoning into small models.

🗣️ **Say it aloud:**
- Why did *verifiable* rewards (vs learned reward models) unlock stable long-CoT RL? Connect to reward hacking.
- What's the difference between outcome and process reward models, and the supervision-cost tradeoff?
- What does "CoT unfaithfulness" mean, and why does it complicate both safety and interpretability claims?
- In what sense is best-of-N-with-verifier a scaling *law* — what's on the x-axis?

### 9.2 Post-transformer & hybrid architectures
**Summary:** Attention's O(n²) and unbounded KV cache motivate **state space models** (Mamba/Mamba-2: linear-time, selective constant-size state — the RNN idea reborn with parallel training), the linear-attention revival (GLA, DeltaNet lineage, sparse state expansion), and pragmatic **hybrids** (Jamba/Zamba/Nemotron-H: mostly SSM layers + a few attention layers) — the 2026 answer for long context. **Titans/nested-learning** architectures add neural long-term memory that *learns at test time* — memory as a first-class component. Also: test-time training (TTT) layers. See [Differential Mamba](https://arxiv.org/pdf/2507.06204) and [Sparse State Expansion](https://arxiv.org/pdf/2507.16577) for the flavor of current work.

🗣️ **Say it aloud:**
- What is Mamba's "selectivity" and why was it the missing piece vs earlier SSMs (S4)?
- Fundamental tradeoff: what can attention's cache do that any constant-size state provably cannot? (Exact retrieval of arbitrary past tokens.) Why do hybrids therefore keep a little attention?
- Contrast in-context learning, RAG, fine-tuning, and Titans-style test-time memory as four *kinds* of memory with different persistence and capacity.

### 9.3 World models & video-as-simulation
**Summary:** Genie-class models generate *interactive, playable* environments from prompts; V-JEPA-style models learn predictive representations without pixel-level generation. The bet: modeling how the world evolves under actions is the path to physical understanding and the training ground for embodied agents — 2026's most-watched race ([survey](https://arxiv.org/pdf/2606.00133), [race overview](https://introl.com/blog/world-models-race-agi-2026)). Model-based RL grows up via Dreamer-class agents (learn policy inside the learned model).

🗣️ **Say it aloud:**
- What makes a world model different from a video generator? (Action-conditioning; consistency under intervention.)
- Why does JEPA predict in representation space rather than pixel space — what's wasted by pixel prediction?
- Why are world models a data-efficiency argument for robotics?

### 9.4 Agents as the product layer
**Summary:** Long-horizon autonomous execution (agentic coding is the flagship), tool ecosystems (**MCP**), computer/browser use, multi-agent systems. The 2026 pain points are exactly the employable skills: reliability under compounding errors, **continual learning & persistent memory** (moving past "goldfish" models — a named priority of every major lab), agent evals, and security (prompt injection — Stage 10).

🗣️ **Say it aloud:**
- An agent with 95% per-step reliability runs 30-step tasks: what's the success rate? What design strategies attack this (verification steps, checkpointing, narrower tools)?
- Why is persistent memory harder than bolting a vector DB onto an agent? (Write policies, forgetting, retrieval precision, memory poisoning.)
- Why is prompt injection *the* security problem of the agent era, and why can't better prompting alone fix it?

### 9.5 Efficiency & the small-model counter-trend
**Summary:** Frontier-distilled 1–30B models match last year's giants; on-device AI is real (phones run 3B models); MoE everywhere; FP8/FP4 training; 1M+ token contexts with subquadratic architectures pushing further. The strategic insight: **capability per dollar is falling ~10×/year** — build products assuming today's frontier is next year's commodity.

🗣️ **Say it aloud:**
- Name the three mechanisms behind small-model gains (distillation from frontier teachers, better data, overtraining past Chinchilla) and rank their contributions.
- What does "capability per dollar falls 10×/year" imply for whether to fine-tune vs wait vs prompt-engineer, for a product shipping in 6 months?

### 9.6 Embodied AI
**Summary:** VLA foundation models (π0/OpenVLA lineage) map camera + language → robot actions; cross-embodiment datasets (Open X-Embodiment) transfer skills across robot bodies; diffusion policies handle multimodal action distributions; sim-to-real increasingly runs through world models. Humanoids are the moonshot; dexterity is the bottleneck.

🗣️ **Say it aloud:**
- Why is robot data the binding constraint (vs text's free internet-scale supervision), and what are the three escape routes (teleop scale-up, sim, video-derived world models)?
- Why does a VLA benefit from vision-language *pretraining* — what transfers into action?

### 9.7 AI for science accelerating
**Summary:** Weather (GenCast-class probabilistic forecasts beating NWP), protein/drug design, materials, formal math (LLM + Lean theorem proving), and **scientific agents** that design/run/interpret experiments. For a deeper snapshot of the 2026 discourse: [world models & continual learning breakthroughs](https://www.nextbigfuture.com/2026/04/2026-is-breakthrough-year-for-reliable-ai-world-models-and-continual-learning-prototypes.html).

🗣️ **Say it aloud:**
- Why did weather fall to ML before, say, materials synthesis? (Dense labeled data via reanalysis; fast verification.)
- What makes formal theorem proving a *verifiable-reward* domain, and why does that matter after 9.1?

**How to follow:** read frontier **technical reports** (DeepSeek, Qwen, Llama, Claude, GPT, Gemini families), not the press coverage.

---

# Stage 10 — Trust: Interpretability, Robustness, Alignment, Uncertainty (3–4 weeks + ongoing)

### 10.1 Mechanistic interpretability
**Summary:** Reverse-engineering what networks compute: features (directions in activation space) and circuits (subnetworks implementing algorithms). Core obstacle: **superposition** — models pack more features than dimensions, so neurons are polysemantic. **Sparse autoencoders (SAEs)** decompose activations into interpretable monosemantic features; activation patching establishes causal roles; the logit lens reads intermediate predictions off the residual stream. Anthropic's circuits work is canonical reading. Young field, fast-growing career niche.

🗣️ **Say it aloud:**
- What is superposition and why does it *predict* polysemantic neurons? What pressure creates it (more useful features than dimensions)?
- How does an SAE recover features — what do sparsity and reconstruction each contribute?
- Activation patching: describe the experiment that shows component X causally carries fact Y.
- Why does the residual-stream view (Stage 4.2/5.3) make interpretability tractable at all?

### 10.2 Uncertainty quantification
**Summary:** A model that knows when it doesn't know. **Calibration** (does 80% confidence mean right 80% of the time — measure with reliability diagrams/ECE; fix cheaply with temperature scaling); **deep ensembles** (still the strongest practical UQ); **conformal prediction** (distribution-free coverage guarantees — turn any model into "prediction sets that contain the truth 90% of the time," extremely useful and underused); aleatoric (irreducible noise) vs epistemic (reducible ignorance) uncertainty — they demand different responses.

🗣️ **Say it aloud:**
- Modern nets are systematically *overconfident* — what training dynamics cause this?
- State conformal prediction's guarantee precisely, including the exchangeability assumption and what breaks it (drift, time series).
- Give one operational decision that differs depending on whether uncertainty is aleatoric vs epistemic (hint: "collect more data" only fixes one).

### 10.3 Robustness & distribution shift
**Summary:** Adversarial examples (imperceptible perturbations flip predictions — FGSM/PGD; adversarial training as defense, at a clean-accuracy cost) reveal that learned decision boundaries are strange. More practically ubiquitous: **distribution shift** (covariate/label/concept) and **OOD detection** — every deployed model eventually meets data unlike its training set, and it should flag rather than confidently guess.

🗣️ **Say it aloud:**
- Why do adversarial examples exist — give the high-dimensional-geometry intuition, and why they transfer across models.
- Covariate vs concept shift: define both, give a detector for each.
- Why is max-softmax a weak OOD score, and name one better signal.

### 10.4 LLM safety & security
**Summary:** **Jailbreaks** (bypassing refusal training) and **prompt injection** (hostile instructions hidden in retrieved/browsed content hijack the agent — *the* unsolved security problem of the agent era; unlike SQL injection there is no clean code/data separation inside a prompt). Hallucination measurement/mitigation, red-teaming as practice, dangerous-capability evals. If you build agents, this is not optional.

🗣️ **Say it aloud:**
- Prompt injection vs jailbreak: different attacker, different victim — explain precisely.
- Why can't "just prompt it to ignore injected instructions" work? What *architectural* mitigations exist (privilege separation, tool allowlists, human gates)?
- Design aloud a red-team plan for an email-reading agent.

### 10.5 Alignment fundamentals
**Summary:** Reward hacking (optimizing the measure, not the goal — Goodhart), sycophancy (RLHF's signature failure), scalable oversight (how do humans supervise superhuman work?), constitutional AI (models critique/revise against principles), and the deceptive-alignment concern (behaving well only while watched — motivating interpretability as verification). Also here: fairness, privacy (DP, membership inference), and the EU-AI-Act-era regulatory landscape.

🗣️ **Say it aloud:**
- Give one concrete published example of reward hacking, and explain it as Goodhart's law.
- Why does RLHF *systematically* produce sycophancy — trace the incentive.
- What is the scalable-oversight problem in one sentence, and one proposed approach (debate, decomposition, RLVR where verifiable)?

**Milestone:** Train SAEs on a small transformer's activations and find interpretable features; **or** wrap any earlier project in conformal prediction and empirically validate its coverage guarantee.

---

# Stage 11 — Research Skills & Staying Current (permanent habit)

**Summary:** The field produces hundreds of papers daily; pros survive via filtering systems and reading protocols. Three-pass paper reading (abstract/figures → method with margin questions → re-derive or re-implement); reproduce one paper per quarter (reproduction is the fastest teacher in existence); write publicly (blog posts of negative results included — honesty compounds reputation); contribute to open source (HF ecosystem, vLLM, PyTorch, TRL/Axolotl — the highest-signal resume line short of a paper).

**Filtering system:** arXiv cs.LG/CL/CV via alphaXiv-style tools; blogs — Lilian Weng, Sebastian Raschka's *Ahead of AI*, Nathan Lambert's *Interconnects*, Chip Huyen, lab blogs; Karpathy's channel for canonical explanations; skim NeurIPS/ICML/ICLR/CVPR/ACL orals & best-paper lists; **frontier model technical reports above all** — the richest public documentation of what actually works at scale.

🗣️ **Say it aloud (about any paper you claim to have read):**
- What problem, in one sentence? What's the *one* new idea over prior work?
- What would falsify the claim? Which ablation is missing?
- What's the compute budget, and does the comparison control for it? (The most common hidden confound in the literature.)
- Could you reproduce the core result at 1/100 scale this weekend? What would you expect to still hold?

---

# The mindset rules (read when discouraged)

1. **Implementation beats intuition beats memorization.** If you haven't coded it, you don't know it.
2. **If you can't say it aloud, you don't understand it.** The 🗣️ questions are the curriculum, not decoration.
3. **Baselines first, always.** Logistic regression / gradient boosting is the honest yardstick for any deep model.
4. **Look at your data.** More projects die from data bugs than architecture choices.
5. **Overfit one batch first.** The universal sanity check.
6. **The field moves fast; fundamentals move slowly.** The 2026 frontier is built from the same bricks as 2016 — attention, backprop, optimization, probability. Invest in bricks.
7. **Compute is a constraint, not an excuse.** Every milestone here except frontier pretraining fits on Colab/Kaggle/cheap cloud GPUs.
8. **Ship things.** A deployed, documented, slightly-scruffy project beats a perfect private notebook.

---

*Next: the [Model Training Mastery track](./MODEL_TRAINING_MASTERY.md) — run it in parallel from Stage 5, finish its Gauntlet, then take on its problem statement and the [GLOF capstone](./PROBLEM_STATEMENT.md).*
