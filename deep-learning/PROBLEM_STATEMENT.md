# The Problem: An Early-Warning System for Glacial Lake Outburst Floods (GLOFs) in the Himalayas

> **A genuinely unsolved, real-world problem that exercises nearly every concept in the [roadmap](./ROADMAP.md) — vision, time series, transformers, graphs, physics-informed learning, self-supervision, generative models, uncertainty quantification, foundation models, edge deployment, and agents.**
>
> This document is a **manual for how to approach it** — the scaffolding, not the solution. The solution does not exist yet. That's the point.

---

## 1. The problem, in plain language

High in the Himalayas, glaciers are melting and leaving behind thousands of lakes dammed by unstable walls of loose rock and ice (moraines). When such a dam fails — triggered by an avalanche, an ice collapse, heavy rain, an earthquake, or slow internal erosion — millions of cubic meters of water are released within minutes. The resulting flood wave travels down valleys at tens of km/h, destroying everything for up to hundreds of kilometers downstream.

This is not hypothetical:

- **October 2023, South Lhonak Lake, Sikkim, India:** a GLOF destroyed the 1,200 MW Teesta-III hydropower dam and killed ~180+ people. Warning time for downstream communities: effectively **zero**, despite the lake being *known and monitored* as high-risk for over a decade.
- There are **~7,500+ glacial lakes across the Hindu Kush Himalaya**, thousands more in the Andes and Central Asia. Studies estimate **15 million people live in GLOF-exposed valleys** worldwide.
- Climate warming is growing these lakes faster than anyone can field-survey them.

### Why it is *unsolved* (not just "hard")

1. **Extreme rarity + extreme stakes.** Only a few dozen well-documented GLOF events exist with good data. You cannot train a classifier on 40 positive examples of a phenomenon with thousands of interacting variables. This is the *small-N, high-dimensional, high-stakes* regime — the frontier of what ML can do.
2. **No labeled precursors.** We don't reliably know what the *early signatures* of dam failure are. Domain scientists hypothesize (lake growth acceleration, ice-cliff calving, slope creep, thermokarst), but nobody has a validated precursor model.
3. **Multimodal, asynchronous, gappy data.** Optical satellites are blocked by clouds exactly when it matters (monsoon). SAR sees through clouds but is noisy and hard to interpret. In-situ sensors are sparse, break in extreme cold, and lose connectivity. Any real system must fuse modalities that arrive at different rates with different failure modes.
4. **The physics is only partially known.** Moraine-dam stability involves glaciology, permafrost mechanics, hydrology, and slope stability — coupled processes with no complete simulator. Pure physics can't solve it; pure data can't either. It *demands* hybrid approaches.
5. **Deployment is brutal.** The end of the pipeline is a siren in a village with intermittent power and a district officer who needs a probability they can trust. False alarms destroy credibility; missed alarms destroy lives. Calibration and uncertainty are not academic here.
6. **It generalizes.** Solve the architecture for this and you've built the template for landslides, flash floods, dam failures, wildfire ignition — the whole class of *rare catastrophic geohazard prediction*. This is an open research + engineering frontier with active work (ICIMOD, NASA/ISRO NISAR mission, national programs) but **no deployed learning-based GLOF early-warning system exists anywhere as of 2026.**

### The concrete goal

> Build a system that, for any monitored glacial lake, continuously outputs a **calibrated hazard score with lead times of hours (rapid-onset triggers) to months (slow-building instability)**, fused from satellite imagery, weather, seismic, and in-situ sensor data — and quantify its own uncertainty honestly enough to drive real evacuation decisions.

You will not fully "solve" this. You *can* make genuine, publishable, potentially deployable progress on well-chosen sub-problems — and each sub-problem is a roadmap stage in disguise.

---

## 2. Why this problem covers your entire roadmap

| Roadmap stage | Where it shows up in this problem |
|---|---|
| 0–1. Math, classical ML | Baselines (logistic regression / gradient boosting on hand-crafted lake features), survival analysis, extreme-value statistics for rare events |
| 2–3. NN fundamentals, training craft | Every model below; heavy class-imbalance handling, careful validation design |
| 4. CNNs / segmentation | Lake delineation & growth tracking from Sentinel-2 imagery (U-Net/SAM-class) |
| 4–5. Sequence models & Transformers | Time-series transformers on sensor + weather streams; long-context modeling of decades of lake evolution |
| 5. Foundation models, LoRA, RAG | Fine-tuning geospatial foundation models (Prithvi/Clay-class) with LoRA; LLM agent that compiles historical GLOF reports into a structured database (RAG over scientific literature) |
| 5. Self-supervised learning | Pretraining on millions of *unlabeled* satellite tiles — your escape hatch from label scarcity |
| 6. Generative models | Diffusion models for cloud-gap infilling of optical imagery; generating synthetic failure scenarios from physical simulators for data augmentation |
| 7. GNNs | River-network graphs for downstream flood-wave propagation; sensor networks as graphs |
| 7. Physics-informed / neural operators | PINNs & FNOs as fast surrogates for dam-breach and flood-routing simulations |
| 7. Time-series & weather models | Precipitation nowcasting (GraphCast/GenCast-class inputs), anomaly detection on sensor streams |
| 7. RL | Optimal sensor-placement / monitoring-budget allocation as a sequential decision problem |
| 8. Systems & edge | Quantized models on solar-powered edge devices at the lake; bandwidth-starved inference |
| 9. Frontier | World-model-style predictive simulation of lake basins; test-time compute for high-stakes case-by-case analysis; multimodal fusion architecture |
| 10. Trust | Conformal prediction for coverage-guaranteed alerts; calibration; OOD detection (every lake is partly out-of-distribution); interpretability for scientist trust |
| 11. Research skills | This is publishable work; the domain literature (glaciology + ML) must be read and synthesized |

---

## 3. The Approach Manual

**Structure:** eight phases. Each phase states its *objective*, *key questions to answer yourself*, *suggested tools/data*, and a *checkpoint* — a concrete artifact proving the phase is done. Phases 1–3 are achievable on a laptop + free data. Deliberately, I tell you *what to figure out*, not the answers.

---

### Phase 0 — Become 20% domain expert (2–3 weeks)

**Objective:** ML applied to a domain you don't understand produces confident nonsense. Learn enough glaciology to know what a moraine dam is, what triggers failures, and what has already been tried.

**Do:**
- Read the post-event analyses of South Lhonak 2023 (multiple papers exist — find them on Google Scholar), the Chamoli 2021 rock-ice avalanche, and Lake Palcacocha (Peru). These three case studies teach you the failure taxonomy.
- Read ICIMOD's glacial-lake inventories and any national GLOF-risk assessments (India's NDMA guidelines, Nepal's DHM reports).
- Build a one-page **causal diagram**: what physical processes lead to dam failure, what observable signals each process might emit, and which sensor/satellite could see each signal. This diagram is your project's constitution — every model you build later should map to an edge in it.

**Key questions to answer:**
- What distinguishes lakes that failed from similar lakes that didn't? (Hint: the literature disagrees — that disagreement is your opportunity.)
- What lead times do different trigger types allow? (An avalanche-triggered surge gives minutes; melt-driven dam degradation gives months.)
- Who would *use* your system's output, and what decision does each user make?

**Checkpoint:** the causal diagram + a written 2-page problem framing, including your chosen study region (suggestion: Sikkim/Eastern Himalaya — well-documented disaster, active monitoring interest, Indian data access).

---

### Phase 1 — Data foundation (3–5 weeks)

**Objective:** assemble a reproducible, versioned multimodal dataset for ~50–200 lakes over 10+ years. This phase is 40% of the total real-world work; treat it as first-class engineering, not a chore.

**Data sources (all free):**
| Modality | Source | Notes |
|---|---|---|
| Optical imagery | **Sentinel-2** (10 m, 5-day revisit, 2015–), Landsat (30 m, 1972–!) | Google Earth Engine or Microsoft Planetary Computer for access without downloading terabytes |
| SAR (cloud-proof) | **Sentinel-1** | Learn what backscatter and coherence mean *before* modeling; NISAR (launched 2025) is the future here |
| Elevation | Copernicus DEM 30 m, HMA 8 m DEMs | Lake volume needs bathymetry — mostly unavailable; you'll need empirical area→volume scaling relations (find them in the literature) |
| Weather | **ERA5 reanalysis** (hourly, 1940–), IMD gridded data | Temperature, precipitation, freezing level height |
| Seismic | IRIS/FDSN open waveforms | Regional stations; GLOFs and their triggers have seismic signatures |
| Lake inventories | ICIMOD, GLIMS, RGI, published GLOF event databases (e.g., the "GLOFsdatabase"/Veh et al. compilations) | Your ~40–60 positive labels live here |
| Terrain context | Glacier outlines (RGI), permafrost maps, land cover | Static features matter |

**Key questions to answer:**
- What is your *unit of prediction*? (Lake-month? Lake-day? Event-vs-nonevent lake?) This single choice shapes everything downstream — think hard, write down the tradeoffs.
- How will you handle the fact that "no recorded GLOF" ≠ "no GLOF" for remote lakes in the 1980s–90s? (Label noise in the negatives.)
- How do you split train/validation/test **without leakage**? Random splits are wrong here twice over: spatially (nearby lakes correlate) and temporally (you can't train on 2020 to predict 2015). Design a *spatiotemporal blocked split* and defend it in writing.

**Checkpoint:** a documented data pipeline (GEE/Planetary Computer scripts → cloud-optimized storage → versioned with DVC or similar) + an EDA notebook showing lake-area time series for 20 lakes, including at least 2 that later burst.

---

### Phase 2 — Baselines or nothing (2–3 weeks)

**Objective:** establish the honest yardsticks every deep model must beat. Skipping this phase is the #1 way applied-ML projects end up as self-deception.

**Build, in order:**
1. **Static susceptibility baseline:** gradient boosting on hand-crafted per-lake features (area, growth rate, dam type, slope above lake, distance to steep ice, seismic zone). This replicates what the glaciology literature already does — your first result is *reproducing the state of the art*, which is a feature, not a bug.
2. **Simple temporal baseline:** anomaly detection on lake-area time series (rolling z-scores, change-point detection).
3. **Climatology baseline:** predict hazard from season + weather percentiles alone.

**Key questions:**
- What metric actually matters? Accuracy is meaningless at ~0.1% event rate. Investigate: precision-recall AUC, **recall at fixed false-alarm budget** (e.g., "catch X% of events with ≤ N false alarms per lake per year"), and **lead-time-weighted** scores. Define your headline metric now and never move the goalposts.
- What does the ROC of *published* susceptibility indices look like on your data?

**Checkpoint:** a results table — every later model gets a row in this table or it doesn't exist.

---

### Phase 3 — Perception: teach a model to watch lakes (4–6 weeks)

**Objective:** automated, all-weather monitoring of every lake — the "eyes" of the system.

**Sub-problems (each is a self-contained project):**
1. **Lake segmentation & area tracking** from Sentinel-2: fine-tune a U-Net or SAM-class model; validate against manually digitized outlines. Then the harder, more valuable version: segmentation from **Sentinel-1 SAR** so monitoring survives the monsoon.
2. **Self-supervised pretraining:** you have millions of unlabeled Himalayan image tiles and only hundreds of labels. This is the textbook setting for MAE/DINO-style pretraining or fine-tuning an existing **geospatial foundation model** (Prithvi, Clay, SatMAE) with LoRA. Measure: how much does pretraining improve segmentation with only 100 labels?
3. **Cloud-gap infilling (generative):** train a diffusion or SAR→optical translation model to estimate lake state under cloud. *Critical trap to think about:* how do you prevent the infilling model from hallucinating "normal" conditions during exactly the anomalous events you care about? (Sit with this question — it's deep, and it's the kind of thing a reviewer or a disaster-management official will ask.)
4. **Precursor change detection:** beyond area — ice-cliff retreat, slope deformation (SAR interferometry/coherence changes), new drainage channels. Nobody has a labeled dataset of these; consider weak/self-supervised change detection and validate qualitatively on the known pre-2023 South Lhonak imagery. **If you find a visual precursor signature at South Lhonak that appears months before the event, that alone is a publishable result.**

**Checkpoint:** an automated pipeline that, given any lake coordinate, produces a 10-year monthly time series of area + change features, robust to clouds — plus the label-efficiency curve from sub-problem 2.

---

### Phase 4 — Dynamics: modeling evolution and precursors (5–8 weeks)

**Objective:** move from *watching* to *anticipating*. This is the scientific heart of the project.

**Approach ladder (climb it; don't jump to the top):**
1. **Per-lake sequence models:** transformer or SSM (Mamba-class) encoders over the multimodal time series (lake features + weather + seismicity) → hazard score. Compare against Phase-2 baselines *at matched false-alarm budgets*.
2. **Multimodal fusion:** modalities arrive at different rates (weather hourly, optical ~weekly, SAR ~6-daily, seismic continuous). Investigate fusion strategies — early vs. late vs. cross-attention with modality/time embeddings; how to handle missing modalities at inference (they *will* be missing). This is an open research design space; your comparison of fusion strategies under realistic missingness is itself a contribution.
3. **Rare-event learning strategy** — the crux. Directions to explore (evaluate at least three):
   - **Surrogate/proxy tasks:** train to predict *abundant* related targets (lake growth next month, seasonal drainage events, small non-catastrophic drawdowns) and transfer to the rare target. Which proxies transfer? Unknown — find out.
   - **Physics-informed constraints:** encode dam-stability physics (freeboard, overtopping thresholds, simple slope-stability relations) as loss terms or architectural priors, so the model interpolates plausibly where data is absent.
   - **Simulation-augmented training:** use open hydraulic models (HEC-RAS, r.avaflow) to simulate thousands of synthetic breach scenarios across real DEMs; train on synthetic, adapt to real (sim-to-real is a studied problem — read that literature). A **neural operator (FNO)** surrogate of the simulator gives you 1000× speedup and enables ensembles.
   - **Extreme-value / survival framing:** model time-to-failure with censored observations instead of binary classification. The statistics of extremes literature (EVT) exists for exactly this regime — most ML people ignore it; don't.
   - **Cross-domain transfer:** landslides and dam failures have far more recorded events. Does a precursor model pretrained on those transfer to GLOFs?
4. **Graph propagation model:** given a breach, a GNN over the river-network graph (nodes = reach segments from the DEM) predicting flood-wave arrival time and depth downstream — trained on simulator outputs. This converts "the lake burst" into "village X has 47 minutes," which is the number that saves lives.

**Key questions:**
- What lead time can each signal physically support? Build separate heads for "months-scale susceptibility drift" vs. "hours-scale trigger response" rather than one confused model.
- How do you validate *precursor discovery* when ground truth precursors are unknown? (Retrospective case studies + domain-scientist review + held-out events. You have ~5–10 well-imaged historical events for true out-of-sample tests. Spend them wisely — like a startup spends runway.)

**Checkpoint:** a retrospective "hindcast" report: for each held-out historical GLOF, what would your system have said 1 year / 1 month / 1 week / 1 day before? Honest plots, including the failures.

---

### Phase 5 — Trust: uncertainty, calibration, interpretability (3–4 weeks, then permanent)

**Objective:** an alert nobody trusts is an alert nobody acts on. This phase turns scores into decisions.

**Do:**
- **Calibrate:** reliability diagrams, temperature scaling; report ECE alongside every headline metric.
- **Conformal prediction:** wrap your hazard model to get distribution-free coverage guarantees ("with 90% confidence the risk exceeds threshold τ"). Investigate conformal methods for time series (standard exchangeability assumptions break — there's active literature on this).
- **Decompose uncertainty:** epistemic (this lake looks unlike anything in training → deep ensembles / evidential methods) vs. aleatoric (inherently unpredictable trigger). These demand different operational responses: epistemic uncertainty says "send a field team," aleatoric says "widen the alert threshold."
- **OOD detection:** flag lakes outside the training distribution rather than scoring them confidently.
- **Interpretability:** attribution over input modalities/time (which signal drove this alert?); a domain scientist must be able to audit any alarm. If your model flags a lake, it should be able to say "because area grew 12% since June while coherence dropped on the north moraine slope."
- **Decision layer:** convert calibrated probabilities + cost asymmetries (false alarm ≪ missed event, but repeated false alarms erode compliance — model that erosion explicitly) into tiered alert levels. This is decision theory, not ML, and it's where the system succeeds or dies.

**Checkpoint:** an "alert dossier" auto-generated for one lake: score, uncertainty decomposition, driving evidence, recommended tier — reviewed by (ideally) an actual geoscientist. Cold-email one; researchers at ICIMOD, IIT, or WIHG respond to serious students more often than you'd expect.

---

### Phase 6 — Systems: make it run in the real world (3–5 weeks)

**Objective:** the model is 20% of the system.

**Do:**
- **Automated ingestion:** new Sentinel scenes trigger processing within hours (event-driven pipeline; monitor for silent data-source failures — satellites have outages too).
- **Edge tier:** design (even if only prototyped on a Raspberry Pi) the at-lake node: camera + water-level + geophone, running a quantized (int8/4-bit) anomaly detector locally, transmitting *only anomalies* over LoRa/satellite uplink. Power budget math included. The 2023 Sikkim lesson: the cloud pipeline is worthless if the last-mile link is the bottleneck — the fast-trigger path must work *without* the cloud.
- **Drift monitoring:** glaciers are non-stationary by definition; your training distribution decays every year. Monitor feature drift and score drift; define retraining triggers.
- **An LLM agent layer (optional, current-gen):** an agent that monitors system outputs, cross-references new satellite anomalies against the scientific literature and news reports (RAG), drafts alert dossiers for human review, and answers analyst questions over the whole database. Agents as *analyst force-multiplier*, not decision-maker.

**Checkpoint:** a live (or faithfully simulated) end-to-end run: new imagery in → dossier out, with latency and cost measured; edge prototype detecting a staged anomaly on desk hardware.

---

### Phase 7 — Evaluate like lives depend on it, then write it up

**Objective:** honest final evaluation + communication.

**Do:**
- **The golden test:** full-system hindcast on held-out events *never touched during development* (you reserved them in Phase 1, right?). Report recall-at-false-alarm-budget, lead-time distributions, and calibration — with confidence intervals (bootstrap over lakes).
- **Ablations:** which modality, which fusion choice, which rare-event strategy actually mattered? One table.
- **Failure analysis:** the events you missed and the false alarms you raised, each with a root-cause narrative. This section is worth more than your best metric.
- **Write-up:** a technical report/preprint + a public blog post + the open-source pipeline. Target venues if you go academic: *NeurIPS/ICLR workshops on climate & ML (e.g., Tackling Climate Change with ML)*, *Natural Hazards and Earth System Sciences*, AGU. Even a strong negative result ("visual precursors are not detectable at Sentinel resolution; here's the resolution that would be needed") is a real contribution here.

---

## 4. Suggested execution order vs. your roadmap

You do **not** need the whole roadmap before starting. Interleave:

- After roadmap **Stage 3** → do Phases 0–2 (domain, data, baselines)
- After **Stage 4** (CNNs/segmentation) → Phase 3.1–3.2
- After **Stage 5** (transformers, SSL, LoRA) → Phase 3.2–3.4 and Phase 4.1–4.2
- After **Stage 6** (generative) → Phase 3.3 and simulation augmentation in 4.3
- After **Stage 7** (GNNs, PINNs, time series) → Phase 4.3–4.4
- After **Stage 8** (systems) → Phase 6
- After **Stage 10** (trust) → Phase 5 (though read about calibration early)

## 5. Traps I will name now so they don't kill you later

1. **Leakage via space and time.** The most common fatal flaw in geohazard ML papers. Blocked splits, always.
2. **Evaluating on the training distribution of lakes.** Your system's real job is the lake it *hasn't* seen. Hold out entire regions.
3. **Optimizing the wrong metric.** ROC-AUC looks great at 0.1% base rates while the system is operationally useless. Fix the false-alarm budget first.
4. **Hallucinating infill.** Generative gap-filling that smooths away anomalies is worse than missing data — it's confident missing data.
5. **Trusting labels.** GLOF event databases disagree with each other. Audit your positives by eye in the imagery.
6. **Building the ML before the causal diagram.** Models divorced from physical mechanism don't extrapolate, and this problem is *all* extrapolation.
7. **Solo-hero mode.** Find one glaciologist/hydrologist collaborator. One hour of their time will save you a month of yours.

---

## 6. What "success" realistically looks like

- **3 months in:** reproducible multimodal dataset + baselines + a SAR-robust lake-monitoring pipeline. Already a strong portfolio project.
- **6–9 months in:** a hindcast showing your fused model beats published susceptibility indices at fixed false-alarm budgets, with calibrated uncertainty. Workshop-paper territory.
- **12+ months in:** precursor findings on historical events, a simulation-augmented rare-event framework, an edge prototype — genuine research-frontier contribution, and a system worth showing to ICIMOD/NDMA-type agencies.

The full problem — a trusted, deployed, pan-Himalayan early-warning network — will take the field years and many people. But every phase above produces standalone value, and the person who has walked this manual end-to-end will have *applied* essentially every major concept in modern deep learning to something that matters.
