# Research and implementation references

Primary research and official documentation checked on 2026-09-13. These sources support particular primitives or evaluation cautions; they do not validate the complete proposed AHAS system. The default thresholds, module boundaries, fixture constructions, and report design in this package are project proposals.

URLs are provided as literal references so another agent can retrieve the original material. No papers, research datasets, package source, or pretrained models are bundled.

## S1 — Character n-gram stylometry

Sapkota, Bethard, Montes, and Solorio (2015), *Not All Character N-grams Are Created Equal: A Study in Authorship Attribution*. NAACL, pp. 93–102.

`https://aclanthology.org/N15-1010/`

Research motivation for character-level profiles and the relevance of punctuation/affix information. V1 uses ordinary n-gram counts and explicitly does not reproduce every subgroup or claim the paper's classification results.

## S2 — Reducing topical information with text distortion

Stamatatos (2017), *Authorship Attribution Using Text Distortion*. EACL, pp. 1138–1149.

`https://aclanthology.org/E17-1107/`

Research motivation for a masked representation. V1's fixed curated-function-word mask is its own fully specified adaptation, not the original paper's frequency-selected experimental configuration. Topic neutrality is not guaranteed.

## S3 — Function words

Kestemont (2014), *Function Words in Authorship Attribution. From Black Magic to Theory?* Workshop on Computational Linguistics for Literature, pp. 59–66.

`https://aclanthology.org/W14-0908/`

Background for function-word features. No particular word or function-word fraction identifies a human, a bot, or an author.

## S4 — Delta and stylometric reference implementations

Eder, Rybicki, and Kestemont (2016), *Stylometry with R: A Package for Computational Text Analysis*. The R Journal 8(1), pp. 107–121. Also the official `stylo` Delta documentation.

`https://journal.r-project.org/articles/RJ-2016-007/`

`https://search.r-project.org/CRAN/refmans/stylo/html/dist.delta.html`

Reference for classical distance methods and their variations. AHAS specifies a classic mean absolute standardized-frequency difference. Its toy reference is only an arithmetic input; no validated reference corpus is bundled.

## S5 — Penalized change-point optimization

Killick, Fearnhead, and Eckley (2012), *Optimal Detection of Changepoints With a Linear Computational Cost*. Journal of the American Statistical Association 107(500), pp. 1590–1598.

`https://arxiv.org/abs/1101.1438`

Original PELT method. It solves a segmentation optimization problem under specified costs/penalties; it is not by itself a test that an account changed author.

## S6 — PELT implementation parameters

Official `ruptures` documentation, *Linearly penalized segmentation (Pelt)*.

`https://centre-borelli.github.io/ruptures-docs/user-guide/detection/pelt/`

Documents `min_size`, `jump`, and method use. Configure these explicitly. AHAS's scaling, family weights, penalty grid, and minimum-data defaults remain project design choices to evaluate.

## S7 — Cosine distance

Official SciPy documentation, `scipy.spatial.distance.cosine`.

`https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.cosine.html`

Independent numerical reference for cosine calculations. AHAS adds explicit zero-vector abstention and evidence requirements.

## S8 — Jensen–Shannon distance

Official SciPy documentation, `scipy.spatial.distance.jensenshannon`.

`https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jensenshannon.html`

Returns the square root of Jensen–Shannon divergence and supports an explicit logarithm base. AHAS specifies base 2 and a residual OTHER_WORD category.

## S9 — Shingling, resemblance, and containment

Broder (1997), *On the Resemblance and Containment of Documents*.

`https://www.cs.princeton.edu/courses/archive/spr05/cos598E/bib/broder97resemblance.pdf`

Primary source for document shingling and set-based resemblance/containment. AHAS initially computes exact set overlap rather than the paper's scalable sampling sketches. Shingle overlap and a contiguous shared passage are different measurements.

## S10 — Data leakage and evaluation hygiene

Official scikit-learn documentation, *Common pitfalls and recommended practices*, especially data leakage.

`https://scikit-learn.org/stable/common_pitfalls.html`

Motivation for separating development from held-out evaluation and keeping fitted preprocessing/reference choices from seeing evaluation information. AHAS's proposed account/thread/source/duplicate-group split discipline is a task-specific evaluation design.

## S11 — AI-text detector validation difficulty

Dugan et al. (2024), *RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors*. ACL, pp. 12463–12492.

`https://aclanthology.org/2024.acl-long.674/`

The benchmark evaluates varied models, decoding settings, domains, and perturbations. It supports the decision not to treat a small set of stylometric clues as a validated AI detector. AHAS V1 implements no AI-writing classifier.

## S12 — UTC datetime handling

Official Python 3.12 documentation, `datetime`.

`https://docs.python.org/3.12/library/datetime.html`

Implementation reference for aware timestamps and timedeltas. AHAS deliberately uses fixed supplied times and integer microseconds rather than the current clock or local timezone.

## S13 — JSON serialization

Official Python 3.12 documentation, `json`.

`https://docs.python.org/3.12/library/json.html`

Documents sorted keys, separators, non-finite-number handling, and decoder hooks. A pinned encoder plus stable data traversal and explicit exclusions is part of AHAS's reproducibility protocol, not a universal cross-platform canonical-JSON claim.

## S14 — Markdown parsing

Official `markdown-it-py` documentation, *Using markdown_it*, and CommonMark specification 0.31.2.

`https://markdown-it-py.readthedocs.io/en/latest/using.html`

`https://spec.commonmark.org/0.31.2/`

References for token parsing, block maps, syntax, and disabling typography substitutions. The implementation must still define retained-text rules and acknowledge dialect differences. Source excerpts are escaped rather than rendered as trusted HTML.

## S15 — Reddit-derived external style benchmark

PAN 2025, *Multi-Author Writing Style Analysis*, official task description.

`https://pan.webis.de/clef25/pan25-web/style-change-detection.html`

The task uses Reddit comments combined into documents and evaluates sentence-level changes, with differing topical conditions including a same-topic hard setting. It is not a chronological account-history benchmark or bot/AI ground truth. Do not invent account metadata or assume hidden test labels are public.

## S16 — Pinned minimum-segment-size PELT fix

[ruptures PR #383, Fix PELT pruning with minimum segment lengths](https://github.com/deepcharles/ruptures/pull/383), jaykobdetar.

[Exact source commit a28574d9e63b0c2a966e176a1d049d3c9deaaaaf](https://github.com/deepcharles/ruptures/commit/a28574d9e63b0c2a966e176a1d049d3c9deaaaaf).

The PR delays candidate removal until its dominance witness can begin a legal minimum-size replacement segment and admits each feasible candidate once, including an off-grid terminal endpoint. AHAS 1.0.1 backports the exact optimizer method onto locked ruptures 1.1.10; AHAS still restricts production to L2 and jump=1. The PR's own test/performance claims are not substitutes for the local runs recorded in docs/PR383.md.
