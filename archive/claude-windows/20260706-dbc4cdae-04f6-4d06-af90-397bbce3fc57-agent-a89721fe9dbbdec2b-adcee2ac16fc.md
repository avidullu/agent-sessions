# claude-windows / dbc4cdae-04f6-4d06-af90-397bbce3fc57

## Metadata

- Source: `claude-windows`
- Kind: `claude`
- Source file: `C:\Users\avidu\.claude\projects\C--Users-avidu-Projects-badminton-highlight-indexer\dbc4cdae-04f6-4d06-af90-397bbce3fc57\subagents\agent-a89721fe9dbbdec2b.jsonl`
- SHA-256: `adcee2ac16fc253f6ca6dc153d795c4d654fc25e73fd2e068b7e18bcb3c05080`
- Source modified: `2026-07-06T19:39:25+00:00`
- Imported at: `2026-07-08T15:59:36+00:00`
- project: `subagents`
- session_id: `dbc4cdae-04f6-4d06-af90-397bbce3fc57`

## Transcript

### 1. user (2026-07-06T19:34:43.346Z)

Research alternative shuttlecock/ball trackers for badminton as of 2026, to compare against WASB-SBDT. I need falsifiable, citable facts about architecture, accuracy, license, and pretrained-weights provenance for each.

Cover these options:
A. TrackNetV2 (badminton shuttlecock tracking, from the NOL/National Yang Ming Chiao Tung / "CoachAI" lineage) — architecture (heatmap CNN, VGG-style encoder-decoder, multi-frame input), the dataset it introduced (the badminton "Shuttlecock" / "Amateur+Professional" dataset), accuracy/precision/recall/F1 reported, license, weights availability/provenance.
B. TrackNetV3 (e.g. alenzenx/TrackNetV3 or the "TrackNetV3: Enhancing ShuttleCock Tracking with augmentations and rectification" paper) — architecture (adds a motion/rectification/inpainting module), accuracy vs V2 and vs WASB, license, weights provenance, maintenance/recency.
C. MonoTrack (monocular badminton, CVPR workshop 2022) — what it does (shuttle + pose + 3D reconstruction), tracker component, license.
D. YOLO-based shuttlecock detection (YOLOv8 / YOLOv11 trained on shuttlecock) — feasibility, accuracy for a tiny fast-moving object, license (Ultralytics is AGPL-3.0 — confirm), any published shuttlecock YOLO models. Note the AGPL implication for commercial use.
E. Any WASB re-implementations or successor/derived trackers with cleaner licensing.

For each: architecture summary, GPU-friendliness (modern torch? actively maintained?), accuracy vs WASB on the badminton shuttlecock benchmark (WASB claims SOTA — get comparative numbers if published), LICENSE, and pretrained-weights + training-dataset provenance (is the dataset usable commercially?).

Use WebSearch for the GitHub repos and papers (arXiv, papers-with-code). WebFetch the repo pages, LICENSE files, and paper abstracts for exact facts. Be especially careful and specific about licenses (many academic sports-tracking repos have no license or a restrictive one) and about whether the badminton training datasets permit commercial use.

Return a concise bulleted list per option, each fact with a source URL. Flag uncertainties (especially licenses and dataset commercial-use terms) as open questions.

### 2. assistant (2026-07-06T19:34:51.838Z)

I'll research each shuttlecock/ball tracker option systematically. Let me start by loading the web tools and running parallel searches.

### 3. assistant (2026-07-06T19:34:54.408Z)

I have web tools loaded. Let me run parallel searches across all the options to find the primary sources (GitHub repos and papers).

### 4. user (2026-07-06T19:35:01.791Z)

Web search results for query: "MonoTrack monocular badminton shuttle pose 3D reconstruction CVPR workshop 2022"

Links: [{"title":"[PDF] MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | Semantic Scholar","url":"https://www.semanticscholar.org/paper/MonoTrack%3A-Shuttle-trajectory-reconstruction-from-Liu-Wang/1f059b1e177fda42534020d04da00c76e2c6d462"},{"title":"Liu MonoTrack Shuttle Trajectory Reconstruction From Monocular Badminton Video CVPRW 2022 Paper | PDF | Image Segmentation | Accuracy And Precision","url":"https://www.scribd.com/document/628393223/Liu-MonoTrack-Shuttle-Trajectory-Reconstruction-From-Monocular-Badminton-Video-CVPRW-2022-paper"},{"title":"MonoTrack:用单粒羽毛球视频重建航天飞机轨道 (MonoTrack: Shuttle trajectory reconstruction from monocular badminton video) - 专知论文","url":"https://www.zhuanzhi.ai/paper/3c9a07d38ecd50f3f3947feac646d9ad"},{"title":"CVPR 2022 Open Access Repository","url":"https://openaccess.thecvf.com/content/CVPR2022W/CVSports/html/Liu_MonoTrack_Shuttle_Trajectory_Reconstruction_From_Monocular_Badminton_Video_CVPRW_2022_paper.html"},{"title":"Widely Applicable Strong Baseline for Sports Ball Detection and Tracking","url":"https://arxiv.org/pdf/2311.05237"},{"title":"Towards Ball Spin and Trajectory Analysis in Table Tennis Broadcast   Videos via Physically Grounded Synthetic-to-Real Transfer","url":"https://arxiv.org/pdf/2504.19863"},{"title":"[2204.01899] MonoTrack: Shuttle trajectory reconstruction from monocular badminton video","url":"https://arxiv.org/abs/2204.01899"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | Request PDF","url":"https://www.researchgate.net/publication/362900461_MonoTrack_Shuttle_trajectory_reconstruction_from_monocular_badminton_video"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | IEEE Conference Publication | IEEE Xplore","url":"https://ieeexplore.ieee.org/document/9857202/"}]

I found search results for MonoTrack. Here's what the research is about:

MonoTrack presents the first complete end-to-end system for the extraction and segmentation of 3D shuttle trajectories from monocular badminton videos, integrating badminton domain knowledge such as court dimension, shot placement, physical laws of motion, along with vision-based features such as player poses and shuttle tracking.

The researchers found that significant engineering efforts and model improvements are needed to make the overall system robust, and as a by-product of their work, improved state-of-the-art results on court recognition, 2D trajectory estimation, and hit recognition.

The paper was published by Paul Liu and Jui-Hsien Wang in the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops in June 2022.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 5. user (2026-07-06T19:35:02.194Z)

Web search results for query: "TrackNetV2 badminton shuttlecock tracking paper architecture VGG heatmap dataset F1"

Links: [{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network - National Yang Ming Chiao Tung University Academic Hub","url":"https://scholar.nycu.edu.tw/en/publications/tracknetv2-efficient-shuttlecock-tracking-network/"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Papers | HyperAI","url":"https://beta.hyper.ai/en/papers/tracknetv2-efficient-shuttlecock-tracking"},{"title":"GitHub - qaz812345/TrackNetV3: Implementation of paper - TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification · GitHub","url":"https://github.com/qaz812345/TrackNetV3"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with ...","url":"https://people.cs.nycu.edu.tw/~yushuen/data/TrackNetV3.pdf"},{"title":"Figure 3 from TrackNetV2: Efficient Shuttlecock Tracking Network | Semantic Scholar","url":"https://www.semanticscholar.org/paper/TrackNetV2:-Efficient-Shuttlecock-Tracking-Network-Sun-Lin/223c287d516284fec9bd9792ca2805aa0f551fc9/figure/2"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Request PDF","url":"https://www.researchgate.net/publication/350935356_TrackNetV2_Efficient_Shuttlecock_Tracking_Network"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification","url":"https://dl.acm.org/doi/fullHtml/10.1145/3595916.3626370"},{"title":"maskGRU: Tracking Small Objects in the Presence of Large Background   Motions","url":"https://arxiv.org/pdf/2201.00467"},{"title":"CoachAI: A Project for Microscopic Badminton Match Data Collection and   Tactical Analysis","url":"https://arxiv.org/pdf/1907.12888"}]

Based on the search results, here's what I found about TrackNetV2:

## Architecture
The network architecture is composed of VGG16 and upsampling layers as well as U-Net. TrackNetV2 employed the U-Net architecture, with skip connections that fused low-level and high-level features, improving tracking precision.

## Heatmap and Loss Function
The data structure of the heatmap layer was remodeled from a pixel-wise one-hot encoding 3D array to a real-valued 2D array to reduce GPU memory usage. The loss function was redesigned from a RMSE-based function to a weighted cross-entropy based function.

## Dataset
The dataset consists of 55,563 frames from 18 badminton match videos.

## Performance Metrics
The accuracy, precision and recall of TrackNetV2 respectively reach 96.3%, 97.0% and 98.7% in the training phase and 85.2%, 97.2% and 85.4% in a test on a brand new match. According to performance comparisons on the Shuttlecock Trajectory Dataset, TrackNetV2 achieved an F1 score of 97.03%.

## Speed Improvement
The processing speed was improved from 2.6 FPS to 31.8 FPS by reducing the input image size and re-engineering the network from a Multiple-In Single-Out (MISO) design to a Multiple-In Multiple-Out (MIMO) design.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 6. user (2026-07-06T19:35:02.346Z)

Web search results for query: "TrackNetV3 shuttlecock tracking rectification inpainting alenzenx GitHub paper"

Links: [{"title":"shuttlecock-tracking · GitHub Topics · GitHub","url":"https://github.com/topics/shuttlecock-tracking"},{"title":"GitHub - qaz812345/TrackNetV3: Implementation of paper - TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification · GitHub","url":"https://github.com/qaz812345/TrackNetV3"},{"title":"GitHub - nickluo/TrackNetV3: TrackNetV3 modified version (TensorRT INT8 Optimization) · GitHub","url":"https://github.com/nickluo/TrackNetV3"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with ...","url":"https://people.cs.nycu.edu.tw/~yushuen/data/TrackNetV3.pdf"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification","url":"https://dl.acm.org/doi/fullHtml/10.1145/3595916.3626370"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification - National Yang Ming Chiao Tung University Academic Hub","url":"https://scholar.nycu.edu.tw/en/publications/tracknetv3-enhancing-shuttlecock-tracking-with-augmentations-and-/"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification | Proceedings of the 5th ACM International Conference on Multimedia in Asia","url":"https://dl.acm.org/doi/10.1145/3595916.3626370"},{"title":"TrackNetV3/train.py at master · qaz812345/TrackNetV3","url":"https://github.com/qaz812345/TrackNetV3/blob/master/train.py"},{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification | Proceedings of the 5th ACM International Conference on Multimedia in Asia","url":"https://doi.org/10.1145/3595916.3626370"},{"title":"Track Net V3 | PDF","url":"https://www.scribd.com/document/853585931/TrackNetV3"}]

Based on the search results, I found comprehensive information about TrackNetV3:

## Overview

TrackNetV3 is a sophisticated model designed to enhance the precision of shuttlecock localization in broadcast badminton videos, composed of two core modules: trajectory prediction and rectification.

## Key Components

The trajectory prediction module leverages an estimated background as auxiliary data to locate the shuttlecock in spite of the fluctuating visual interferences and incorporates mixup data augmentation to formulate complex scenarios to strengthen the network's robustness.

Given that a shuttlecock can occasionally be obstructed, repair masks are created by analyzing the predicted trajectory, subsequently rectifying the path via inpainting, which process significantly enhances the accuracy of tracking and the completeness of the trajectory.

## Performance

The experimental results illustrate a substantial enhancement over previous standard methods, increasing the accuracy from 87.72% to 97.51%.

## Publication and Code

The paper was published in the Proceedings of the 5th ACM International Conference on Multimedia in Asia (MMAsia 2023) by the Association for Computing Machinery in 2023. The source code is available at https://github.com/qaz812345/TrackNetV3.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 7. user (2026-07-06T19:35:18.367Z)

Web search results for query: "WASB-SBDT shuttlecock ball detection tracking SOTA sports benchmark GitHub license"

Links: [{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Request PDF","url":"https://www.researchgate.net/publication/350935356_TrackNetV2_Efficient_Shuttlecock_Tracking_Network"},{"title":"Widely Applicable Strong Baseline for Sports Ball ...","url":"https://papers.bmvc2023.org/0310.pdf"},{"title":"GitHub - nttcom/WASB-SBDT: [BMVC2023] Widely Applicable Strong Baseline for Sports Ball Detection and Tracking · GitHub","url":"https://github.com/nttcom/WASB-SBDT"},{"title":"(PDF) Widely Applicable Strong Baseline for Sports Ball Detection and Tracking","url":"https://www.researchgate.net/publication/376208967_Widely_Applicable_Strong_Baseline_for_Sports_Ball_Detection_and_Tracking"},{"title":"Daily Papers - Hugging Face","url":"https://huggingface.co/papers?q=ball+action+spotting"},{"title":"Sports Ball Detection And Tracking","url":"https://www.catalyzex.com/s/Sports%20Ball%20Detection%20And%20Tracking"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | Request PDF","url":"https://www.researchgate.net/publication/362900461_MonoTrack_Shuttle_trajectory_reconstruction_from_monocular_badminton_video"},{"title":"Widely Applicable Strong Baseline for Sports Ball Detection and Tracking","url":"https://arxiv.org/pdf/2311.05237"},{"title":"RacketVision: A Multiple Racket Sports Benchmark for Unified Ball and Racket Analysis | Request PDF","url":"https://www.researchgate.net/publication/397895011_RacketVision_A_Multiple_Racket_Sports_Benchmark_for_Unified_Ball_and_Racket_Analysis"},{"title":"WASB-SBDT/GET_STARTED.md at main · nttcom/WASB-SBDT","url":"https://github.com/nttcom/WASB-SBDT/blob/main/GET_STARTED.md"}]

Now let me search for information about the GitHub license for this repository:

Links: [{"title":"GitHub - nttcom/WASB-SBDT: [BMVC2023] Widely Applicable Strong Baseline for Sports Ball Detection and Tracking · GitHub","url":"https://github.com/nttcom/WASB-SBDT"},{"title":"NTT DOCOMO BUSINESS, Inc. · GitHub","url":"https://github.com/nttcom"},{"title":"WASB-SBDT/GET_STARTED.md at main · nttcom/WASB-SBDT","url":"https://github.com/nttcom/WASB-SBDT/blob/main/GET_STARTED.md"},{"title":"nttcom repositories · GitHub","url":"https://github.com/orgs/nttcom/repositories"},{"title":"Sports Ball Detection And Tracking","url":"https://www.catalyzex.com/s/Sports%20Ball%20Detection%20And%20Tracking"},{"title":"(PDF) Widely Applicable Strong Baseline for Sports Ball Detection and Tracking","url":"https://www.researchgate.net/publication/376208967_Widely_Applicable_Strong_Baseline_for_Sports_Ball_Detection_and_Tracking"},{"title":"Licenses | Choose a License","url":"https://choosealicense.com/licenses/"},{"title":"Open Source Licensing Simplified: A Comparative Overview of Popular Licenses | Blog | Endor Labs","url":"https://www.endorlabs.com/learn/open-source-licensing-simplified-a-comparative-overview-of-popular-licenses"},{"title":"The MIT License – Open Source Initiative","url":"https://opensource.org/license/mit"}]

Let me search more specifically for the license file or license information in the WASB-SBDT repository:

Links: [{"title":"Applying the Apache license, version 2.0 | Apache Software Foundation","url":"https://apache.org/legal/apply-license.html"},{"title":"Applying the Apache license, version 2.0 - Apache Infrastructure Website","url":"https://infra.apache.org/apply-license.html"},{"title":"Apache License 2.0 | Software Package Data Exchange (SPDX)","url":"https://spdx.org/licenses/Apache-2.0.html"},{"title":"Assembling LICENSE and NOTICE files - Apache Infrastructure Website","url":"https://infra.apache.org/licensing-howto.html"},{"title":"The Apache License, Version 2.0 - Apache HTTP Server Version 2.4","url":"https://httpd.apache.org/docs/2.4/license.html"},{"title":"licenses/Apache-2.0-License.txt at master · sundarnagarajan/licenses","url":"https://github.com/sundarnagarajan/licenses/blob/master/Apache-2.0-License.txt"},{"title":"Apache License Version 2.0","url":"https://docs.oracle.com/cd/F25388_01/doc.192/f21063/c_apache_license_version_2.0.htm"}]

Let me do a more direct search for WASB-SBDT license information:

Links: [{"title":"GitHub - nttcom/WASB-SBDT: [BMVC2023] Widely Applicable Strong Baseline for Sports Ball Detection and Tracking · GitHub","url":"https://github.com/nttcom/WASB-SBDT"},{"title":"WASB-SBDT/GET_STARTED.md at main · nttcom/WASB-SBDT","url":"https://github.com/nttcom/WASB-SBDT/blob/main/GET_STARTED.md"},{"title":"Basketball and ball tracking · Issue #30 · roboflow/sports","url":"https://github.com/roboflow/sports/issues/30"},{"title":"NTT DOCOMO BUSINESS, Inc. · GitHub","url":"https://github.com/nttcom"},{"title":"loislo (Ilya Tikhonovsky) · GitHub","url":"https://github.com/loislo"},{"title":"nttcom repositories · GitHub","url":"https://github.com/orgs/nttcom/repositories"},{"title":"GitHub - AugustRushG/TOTNet · GitHub","url":"https://github.com/AugustRushG/TOTNet"},{"title":"ntt/LICENSE at master · nokia/ntt","url":"https://github.com/nokia/ntt/blob/master/LICENSE"},{"title":"GitHub - nasa/icc: This three-year project, funded by SSTP and in collaboration with Colorado School of Mines, develops efficient algorithms for communication-aware orbit optimization for multi-spacecraft systems around small bodies. The software release has been approved by the JPL SRA, Brian Morrison (NTR-51071). · GitHub","url":"https://github.com/nasa/icc"},{"title":"icc/README.md at development · nasa/icc","url":"https://github.com/nasa/icc/blob/development/README.md"}]

Based on my web search results, I found comprehensive information about WASB-SBDT. Here's what I found:

## Summary of WASB-SBDT

WASB (Widely Applicable Strong Baseline) is a Sports Ball Detection and Tracking (SBDT) baseline that can be applied to a wide range of sports categories including soccer, tennis, badminton, volleyball, and basketball.

### Key Features:
The method serves as a widely applicable strong baseline (WASB) of SBDT, with datasets and codebase available to promote future SBDT research. Extensive experiments on 5 SBDT datasets from different sports categories demonstrate that WASB achieves substantially better performance than 6 state-of-the-art (SOTA) SBDT methods on all the datasets.

### Repository:
Datasets and codes are available at https://github.com/nttcom/WASB-SBDT.

### License:
According to a GitHub discussion, the WASB-SBDT repository is MIT licensed, which allows for flexible use, modification, and distribution of the code.

### Publication:
The work introduces two novel SBDT datasets, provides new manual annotations, and re-implements all the SOTA methods. The research was published at BMVC 2023 (British Machine Vision Conference).


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 8. assistant (2026-07-06T19:35:23.788Z)

Good, I have a strong foundation. Now let me fetch the actual repo pages and LICENSE files for exact facts. Let me fetch the key primary sources in parallel.

### 9. user (2026-07-06T19:35:32.452Z)

# WASB-SBDT Repository Facts

## License
The repository states "MIT license" in its metadata. The exact badge shown reads: "License: MIT" with reference to "https://opensource.org/licenses/MIT"

## Model Architecture
The page does not provide specific architectural details. It only describes WASB as a "Sports Ball Detection and Tracking (SBDT) baseline."

## Sports & Datasets Covered
The repository covers multiple sports: ⚽ 🎾 🏸 🏐 🏀 (soccer, tennis, badminton, volleyball, basketball). However, the page provides no specific details about badminton-specific performance or datasets.

## Pretrained Weights & Availability
The README states: "Now it contains evaluation codes of pretrained WASB models only." The MODEL_ZOO.md file is referenced but its contents aren't shown in this excerpt. No explicit license statement for weights is provided.

## Training Datasets
The page does not specify which datasets were used for training WASB models.

## PyTorch & Modern Dependencies
The page indicates "Tested with Python3.8, CUDA11.3" and shows badges indicating "Pytorch" but doesn't specify PyTorch version requirements.

## Maintenance Recency
Repository released November 17, 2023, with the last noted update being November 23, 2023 (evaluation code additions).

## TrackNet Comparison on Badminton
No badminton-specific comparison numbers against TrackNet are provided in this excerpt.

### 10. user (2026-07-06T19:35:36.599Z)

# TrackNetV3 - Extracted Facts

## License
**MIT License** - stated in repo footer

## Architecture Components
The model has two core modules:
1. **Trajectory Prediction Module** - uses estimated background as auxiliary data; incorporates mixup data augmentation
2. **Rectification Module** - analyzes predicted trajectory to create repair masks, then rectifies via inpainting

## Pretrained Weights
**Availability:** Yes, downloadable
**Download Link:** "https://drive.google.com/file/d/1CfzE87a0f6LhBp0kniSl1-89zaLCZ8cA/view?usp=sharing"
**Files:** TrackNet_best.pt and InpaintNet_best.pt (unzipped from TrackNetV3_ckpts.zip)
**Provenance:** Maintained by repository author (qaz812345)

## Training Dataset
**Name:** "Shuttlecock Trajectory Dataset"
**Source:** Link provided in references section
**Attributes:** "Frame, Visibility, X, Y" per CSV files
**Commercial Use Terms:** Not explicitly stated in provided content
**License:** Not specified in excerpt

## Performance vs TrackNetV2

| Model | Accuracy | F1 Score |
|-------|----------|----------|
| TrackNetV3 | 97.51% | 98.56% |
| TrackNetV2 | 94.98% | 97.03% |

**Improvement:** ~2.5% accuracy gain, ~1.5% F1 gain

## Technology Stack
- **Python 3.8.7** (modern PyTorch compatible)
- **PyTorch 1.10.0** (current-generation)
- **100% Python codebase**

## Maintenance Status
36 commits in master branch; exact last commit date not provided in excerpt

### 11. user (2026-07-06T19:35:36.697Z)

# TrackNetV3 Project Analysis

## License
**MIT License** - "MIT license" is stated in the repository footer.

## Architecture
TrackNetV3 is described as "a semantic segmentation tracking network" and represents "the first TrackNet using Attention." The repository includes architecture diagrams but specifics are visual rather than textual.

## Pretrained Weights
Available weights achieving 90.53% accuracy: "Click to obtain training weights | 點擊以獲取權重 : 90.53%" via Google Drive link provided in README.

## Training Dataset
- **Size**: "training set = 32,421 images, validation set = 3,717 images, test set = 11,118 images"
- **Domain**: Badminton tracking
- **License**: Not explicitly stated in provided content

## Accuracy
- **TrackNetV3**: "90.53%"
- **TrackNetV2** (baseline): "88.49%"

## Framework & Dependencies
PyTorch installation specified: "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu117"

Python support: "python = 3.7.9~3.9.4"

## Maintenance Status
Repository shows 37 commits with recent activity, including 3 pull requests from community contributors noted as providing "bug fixes or process optimizations."

### 12. assistant (2026-07-06T19:35:43.472Z)

I have both TrackNetV3 variants. Now let me fetch the LICENSE files directly (repo metadata badges can be misleading — I need to confirm the actual LICENSE files exist), and the WASB MODEL_ZOO and the papers for exact provenance. Let me also get the original TrackNetV2 source and the dataset license details.

### 13. user (2026-07-06T19:35:45.607Z)

The server returned HTTP 404 Not Found.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.

### 14. user (2026-07-06T19:35:47.592Z)

The server returned HTTP 404 Not Found.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.

### 15. user (2026-07-06T19:35:52.855Z)

# Summary of WASB-SBDT Paper

## Abstract
The paper presents a "novel Sports Ball Detection and Tracking (SBDT) method that can be applied to various sports categories" using high-resolution feature extraction, position-aware training, and temporal consistency inference.

## Key Results
The authors report that their method achieves results "substantially superior to existing methods on all the sports categories covered by the datasets."

## WASB Architecture
The paper does not provide specific architectural details in the abstract or accessible content. It describes the approach as comprising three components: high-resolution feature extraction, position-aware model training, and temporal consistency inference during inference.

## Badminton Datasets & Comparative Results
Unfortunately, the provided web page content does not include:
- Specific badminton dataset names or sources
- Comparative F1/accuracy metrics versus TrackNetV2 or TrackNetV3
- Detailed benchmark results

The abstract mentions validating on "5 datasets from different sports categories" and that "Datasets and codes are available" at their GitHub repository, but the specific badminton dataset names and comparative numerical results are not present in the excerpt provided.

To obtain these specific details, you would need to access the full paper PDF.

### 16. user (2026-07-06T19:35:58.535Z)

Based on the LICENSE file content provided:

**License Type:** MIT License

**Year:** 2024

**Copyright Holder:** qaz812345

**Exact Quote:** "MIT License

Copyright (c) 2024 qaz812345"

### 17. assistant (2026-07-06T19:36:04.162Z)

TrackNetV3 (qaz812345) confirmed MIT. The WASB LICENSE and MODEL_ZOO paths 404'd — let me find the correct paths. Let me use the GitHub API via the raw content and check the repo structure, plus fetch the WASB paper PDF directly and the MonoTrack paper.

### 18. user (2026-07-06T19:36:08.618Z)

=== https://raw.githubusercontent.com/nttcom/WASB-SBDT/main/LICENSE ===
404: Not Found
=== https://raw.githubusercontent.com/nttcom/WASB-SBDT/main/LICENSE.txt ===
404: Not Found
=== https://raw.githubusercontent.com/nttcom/WASB-SBDT/main/LICENSE.md ===
MIT License

Copyright (c) 2023 NTT Communications Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### 19. user (2026-07-06T19:36:09.955Z)

=== repo tree (top level) ===
    "name": ".gitignore",
    "path": ".gitignore",
    "name": "Dockerfile",
    "path": "Dockerfile",
    "name": "GET_STARTED.md",
    "path": "GET_STARTED.md",
    "name": "LICENSE.md",
    "path": "LICENSE.md",
    "name": "MODEL_ZOO.md",
    "path": "MODEL_ZOO.md",
    "name": "README.md",
    "path": "README.md",
    "name": "src",
    "path": "src",

### 20. assistant (2026-07-06T19:36:17.265Z)

WASB-SBDT LICENSE confirmed: MIT, Copyright (c) 2023 NTT Communications Corporation. Now let me get the WASB MODEL_ZOO (correct path), the WASB paper PDF for exact badminton numbers, MonoTrack repo/license, and the original TrackNetV2 source + dataset license.

### 21. user (2026-07-06T19:36:21.405Z)

=== WASB MODEL_ZOO.md ===
# Model Zoo

We provide model weights of SOTA methods (including WASB) for each dataset.

We also provide a setup script to download all the listed models at once. See [here](https://github.com/starashima/WASB-SBDT_sandbox/blob/main/GET_STARTED.md#model-preparation) for more details.

|                | Soccer | Tennis | Badminton | Volleyball | Basketball |
| -------------- | ------ | ----   | ----      | ----       | ----       | 
| [DeepBall](https://arxiv.org/abs/1902.07304) | [Google Drive](https://drive.google.com/file/d/1u-Y-RnIgu3H7bZCvv9JVQGkYsBRx0XS9/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1h5v5_kUw4c_4Uw7tpKSBSh4bJwlWm8ly/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1b-D2lrNuUNhZ9OPaLSrIjvU86y0OawFI/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1mSWsewoBVAG-EdyypkDk1lhIK915wGmo/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1fUIVCzcKhfY5UiACF5T8mOpkr1x-Gu5C/view?usp=drive_link) | 
| [DeepBall-Large](https://arxiv.org/abs/2311.05237) | [Google Drive](https://drive.google.com/file/d/1-ak_vi8BiY9FoFVccxpYaJI_qJ6RjOxW/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1hpCH6TM1EvoWmu5JZAkthz141DLgxrgn/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1baHb1dtKHkXwQdGH8PB21hbdNVOu1dT1/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1tBLqbiokWpO6Xgh_fsNi-1kn0x6qhOHO/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/11ENjf5sAFkw6-jCGSXGfyU0t35axWdGH/view?usp=drive_link) |
| [BallSeg](https://arxiv.org/abs/2007.11876) | [Google Drive](https://drive.google.com/file/d/1wbuxL-bKpG-OGVYa7BBeWzmzcHKKIAl5/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/14YEAcxwUUgvaL3km07fPSduJLBBNuk_D/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1zey7rEX8orvpT0c1qbD5FsQ93jfBmaMl/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1FLJVwsupt5FXnPxMu41vPDWwIQBtU9d1/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1dTV-udhhO4K0651yRd1tfLhLMjh9uuBM/view?usp=drive_link) | 
| [TrackNetV2](https://ieeexplore.ieee.org/document/9302757) | [Google Drive](https://drive.google.com/file/d/1yTCC_8cWnMCLOpErk6UpepzQD9UF8Wpi/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1BCnmvDX-LZpbkk4vlMEXMm-uzCoqJzDx/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1lCVYzua7jJfuKqvWGypkYqr6PHA1EaPq/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/103jOdYp4k20avid4uyB9USCuwiphI4Kz/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1n-R_T0QyENsArYV8Qn8TneEroQkmYbT6/view?usp=drive_link) |
| [ResTrackNetV2](https://arxiv.org/abs/2311.05237) | [Google Drive](https://drive.google.com/file/d/150_sbSmOXRCMDEJvsIeT7NFURJ_nucTB/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/112qHZpPWgqCeZbbFXC0oRulrVsokzWYZ/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1NUeuFp1xKxLzvGR5RHSFhrI3LvzKbaFo/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1gnd-VbUUGmiB_Obn7WHpmTuhd0zARN5c/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1K0kxE8vdjnLZm7dzGvwVE-nDuzQWn0t9/view?usp=drive_link) | 
| [MonoTrack](https://ieeexplore.ieee.org/document/9857202) | [Google Drive](https://drive.google.com/file/d/1PBVMfjqLFiUN9M_4NkiAW0i_2alEk_vH/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1mC3yWf6ySlzF-1d-s_LNH1QWexHz2M3D/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1b7hDHU6q7HarBOCVSx46_Rurtn1J1Ko9/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/15dNX0oV_YiP7u2SbcyN5b2nNtMwVt3TT/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1uM2FJLG11AtC0fHsurOqBBUuTehRJugs/view?usp=drive_link) | 
| [WASB (Ours)](https://arxiv.org/abs/2311.05237) | [Google Drive](https://drive.google.com/file/d/1pg0MpMtKZ6ziYEr4oyfKYPOO3hjLw94l/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/14AeyIOCQ2UaQmbZLNQJa1H_eSwxUXk7z/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/17Ac0pO5oryh1JwgwTFQTjOKHY3umbDQu/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1M9y4wPJqLc0K-z-Bo5DP8Ft5XwJuLqIS/view?usp=drive_link) | [Google Drive](https://drive.google.com/file/d/1nfECuSyJvPUmz3njZCdFERSQQbERt8FU/view?usp=drive_link) |


=== WASB README (dataset/badminton refs) ===
Code & dataset repository for the paper: **[Widely Applicable Strong Baseline for Sports Ball Detection and Tracking](https://arxiv.org/abs/2311.05237)**
[![arXiv](https://img.shields.io/badge/arXiv-2311.05237-00ff00.svg)](https://arxiv.org/abs/2311.05237) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) ![test](https://img.shields.io/static/v1?label=By&message=Pytorch&color=red)
We present Widely Applicable Strong Baseline (WASB), a Sports Ball Detection and Tracking (SBDT) baseline that can be applied to wide range of sports categories :soccer: :tennis: :badminton: :volleyball: :basketball: .
- [11/21/2023] Evaluation codes of TrackNetV2, ResTrackNetV2 and MonoTrack are added!
- See [MODEL_ZOO.md](./MODEL_ZOO.md) for available model weights.

### 22. user (2026-07-06T19:36:31.451Z)

I cannot extract the requested information from this PDF content because:

1. **The document is heavily encoded/compressed**: The provided text shows raw PDF object streams with compression filters (FlateDecode), making it unreadable without proper PDF parsing tools.

2. **No accessible badminton dataset information**: I cannot locate readable sections containing dataset names, sources, or TrackNetV2 comparisons.

3. **No visible comparative tables**: The encoded streams prevent me from identifying table numbers, performance metrics (F1, precision, recall, accuracy), or specific numerical comparisons.

4. **No architecture details**: I cannot extract backbone information (HRNet or alternatives) from the compressed data.

**To properly analyze this paper, you would need to:**
- Provide the uncompressed/rendered PDF text
- Share the paper's abstract and methods section in plain text
- Or provide a direct link to the paper's published version

If you have access to the readable PDF, please share the relevant sections on the badminton dataset, comparative results table, and model architecture.

[Binary content (application/pdf, 1.1MB) also saved to C:\Users\avidu\.claude\projects\C--Users-avidu-Projects-badminton-highlight-indexer\dbc4cdae-04f6-4d06-af90-397bbce3fc57\tool-results\webfetch-1783366538578-mlblhd.pdf]

### 23. user (2026-07-06T19:36:33.201Z)

Web search results for query: "MonoTrack badminton GitHub repository code release license shuttle tracking"

Links: [{"title":"GitHub - jhwang7628/monotrack · GitHub","url":"https://github.com/jhwang7628/monotrack"},{"title":"(PDF) MonoTrack: Shuttle trajectory reconstruction from monocular badminton video","url":"https://www.researchgate.net/publication/359757180_MonoTrack_Shuttle_trajectory_reconstruction_from_monocular_badminton_video"},{"title":"[2204.01899] MonoTrack: Shuttle trajectory reconstruction from monocular badminton video","url":"https://arxiv.org/abs/2204.01899"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | Request PDF","url":"https://www.researchgate.net/publication/362900461_MonoTrack_Shuttle_trajectory_reconstruction_from_monocular_badminton_video"},{"title":"GitHub - Pratyunmis/Badminton-Shuttle-Tracker: A tested code on Windows(Linux version coming soon) platform for real-time tracking of shuttlecock for badminton playing robot. · GitHub","url":"https://github.com/Pratyunmis/Badminton-Shuttle-Tracker"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | IEEE Conference Publication | IEEE Xplore","url":"https://ieeexplore.ieee.org/iel7/9856930/9856648/09857202.pdf"},{"title":"GitHub - qaz812345/TrackNetV3: Implementation of paper - TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification · GitHub","url":"https://github.com/qaz812345/TrackNetV3"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton video | DeepAI","url":"https://deepai.org/publication/monotrack-shuttle-trajectory-reconstruction-from-monocular-badminton-video"},{"title":"badminton · GitHub Topics · GitHub","url":"https://github.com/topics/badminton?o=desc&s=stars"},{"title":"GitHub - guaneec/badminton: A simple badminton shuttle tracker · GitHub","url":"https://github.com/guaneec/badminton"}]

Based on the search results, I found information about the MonoTrack badminton project:

## MonoTrack Overview

MonoTrack is an end-to-end system for reconstructing 3D and 2D trajectories from broadcast-style badminton videos. The codebase contains the system described in MonoTrack: Shuttle trajectory reconstruction from monocular badminton video.

## GitHub Repository

The official GitHub repository is located at: https://github.com/jhwang7628/monotrack

## Technical Details

The system uses MMPose and MMDet for pose detection, and a modified TrackNet for shuttle tracking.

## Code Implementation

It presents the first complete end-to-end system for the extraction and segmentation of 3D shuttle trajectories from monocular badminton videos, integrating badminton domain knowledge such as court dimension, shot placement, physical laws of motion, along with vision-based features such as player poses and shuttle tracking.

However, the search results do not contain specific information about the code release license for the MonoTrack repository. To find that information, you would need to visit the GitHub repository directly to check the LICENSE file.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 24. assistant (2026-07-06T19:36:37.295Z)

The WASB MODEL_ZOO confirms badminton pretrained weights exist for WASB, TrackNetV2, MonoTrack, etc. The BMVC PDF is compressed — I downloaded it. Let me extract the badminton comparison numbers from the local PDF and the MonoTrack license, plus find the original TrackNetV2 dataset license terms. Let me read the PDF and check MonoTrack's license.

### 25. user (2026-07-06T19:36:40.305Z)

pdftoppm is not installed. Install poppler-utils (e.g. `brew install poppler` or `apt-get install poppler-utils`) to enable PDF page rendering.

### 26. user (2026-07-06T19:36:46.934Z)

=== monotrack LICENSE ===
--- LICENSE ---
Copyright © <YEAR>, Adobe Inc. and its licensors. All rights reserved.

ADOBE RESEARCH LICENSE

Adobe grants any person or entity ("you" or "your") obtaining a copy of these certain research materials that are owned by Adobe ("Licensed Materials") a nonexclusive, worldwide, royalty-free, revocable, fully paid license to (A) reproduce, use, modify, and publicly display the Licensed Materials; and (B) redistribute the Licensed Materials, and modifications or derivative works thereof, provided the following conditions are met:

-      The rights granted herein may be exercised for noncommercial research purposes (i.e., academic research and teaching) only. Noncommercial research purposes do not include commercial licensing or distribution, development of commercial products, or any other activity that results in commercial gain.
-      You may add your own copyright statement to your modifications and/or provide additional or different license terms for use, reproduction, modification, public display, and redistribution of your modifications and derivative works, provided that such license terms limit the use, reproduction, modification, public display, and redistribution of such modifications and derivative works to noncommercial research purposes only.
--- LICENSE.md ---
404: Not Found--- LICENSE.txt ---
404: Not Found--- COPYING ---
404: Not Found=== monotrack root contents ===
    "name": ".gitignore",
    "name": "LICENSE",
    "name": "README.md",
    "name": "badminton-court-detection",
    "name": "court-detection",
    "name": "deprecated",
    "name": "mmpose",
    "name": "modified-tracknet",
    "name": "notebooks",
    "name": "python",
    "name": "setup",
=== monotrack repo meta (license/pushed) ===
  "name": "monotrack",
  "updated_at": "2026-06-23T19:24:38Z",
  "pushed_at": "2023-07-27T16:18:03Z",
  "license": {
    "name": "Other",
    "spdx_id": "NOASSERTION",

### 27. assistant (2026-07-06T19:36:51.185Z)

Critical finding: MonoTrack is under the **Adobe Research License — noncommercial research only**. That's a hard blocker for commercial use. Now let me extract the WASB badminton comparison numbers from the PDF (need a text extraction approach), and pin down the TrackNetV2 original source + the Shuttlecock dataset license. Let me try pdftotext / python and search for the original TrackNetV2 repo.

### 28. user (2026-07-06T19:36:58.627Z)

using pdftotext
Sports ball trajectory depicted in Figure 1 is an important statistic for analytics of various sports such as badminton [83], baseball [74], basketball [24], golf [30], soccer [72, 78], tennis [64], table tennis [18], and volleyball [15]. Several commercial systems like HawkEye1 and KINEXON2 have already been successfully introduced to professional leagues, but they usually require high-cost installation. Computer vision techniques can be an alternative approach to obtain ball trajectories from easily available video data. However, this Sports Ball Detection and Tracking (SBDT) task is challenging due to the small size of a sports ball, its high speed, occlusion, blending in with surroundings, and camera motion [96].
Figure 1: Exemplar ball trajectories extracted from soccer, tennis, badminton, volleyball and basketball videos, respectively. Best viewed in color.
while there are extensive literatures of SBDT methods proposed in the last two decades, most of them cannot be directly applied to different domains, since they are tailor-made for specific sports (e.g., badminton [9], baseball [74], basketball [5, 6, 7, 8, 11], golf [53, 54], soccer [3, 4, 16, 17, 19, 20, 21, 31, 34, 36, 46, 47, 48, 52, 55, 56, 57, 60, 61, 62, 66, 67, 68, 73, 79, 93, 94, 95, 96, 98, 99, 100, 102, 111, 112], tennis [1, 2, 22, 28, 29, 38, 39, 43, 59, 64, 69, 77, 85, 86, 88, 89, 90, 97, 101, 103, 109, 110], table tennis [13, 18, 23, 26, 58, 104, 105, 106], volleyball [10, 12, 14, 15]). Recent approaches [32, 40, 42, 50, 75, 80] based on Convolutional Neural Networks (CNNs) can potentially be used for different ball-games, but unfortunately in their works evaluations are limited to almost one sports category.
is composed of a variant of fully convolutional networks [51], in which intermediate multiscale features are fused in a decoder to extract high-resolution heatmaps representing ball positions. BallSeg [80] is a modification of ICNet [108], so that two consecutive frames can be fed into the model to capture ball dynamics. TrackNet and its variants [32, 50, 75] are based on U-Net [71] architecture, following a multiple-in multiple-out (MIMO) design to efficiently capture ball movement. Usually, training these models inevitably confronts high foreground-background class imbalance, due to the small ball size appeared in sports videos. Existing methods address this issue by adapting the focal loss 3 [49], the combo loss [76] or hard negative mining technique [51]. Notice that in these recent methods, ball dynamics are considered only within frames that are combined in the same batch.
series of HRNet works [82, 92]. HRNet consists of a stem block and multi-stage high-resolution modules
representation while keeping spatial resolution. In this paper we instantiate our HRMs following the small HRNet design5 illustrated in Figure 2: There are 4 stages and each stage consists of parallel sequences of residual blocks [27] followed by a multi-resolution fusion.
5https://github.com/HRNet/HRNet-Image-Classification
To evaluate the wide-applicability of SBDT algorithms, in this work we use 5 SBDT datasets from different sports categories, which are detailed in the followings. Among them, Basketball and Volleyball are newly introduced datasets for SBDT, while the ground truths of Basketball and Soccer are newly annotated by us. Statistics are summarized in Table 1. Soccer [19]. This dataset6 was originally introduced for soccer ball and player tracking from six synchronized videos, and has been used in some SBDT works [41, 42, 84]. Following [41, 42], we use the first four video clips for training and the remaining two clips for testing. However, we found that ball annotations provided in the original dataset are collapsed and do not localize ball position correctly. Therefore, in this work we manually re-annotate ball position to all the frames and use the resulting annotation for training and testing. Tennis [32]. This dataset was introduced along with the TrackNet work [32], but was not used in its experiment. Since there is no common usage for this dataset, we propose to use all the clips included in the first 7 games as a training set, and the remainings as a testing set. Badminton [75]. This dataset was introduced by the TrackNetV2 work [75]. Following the dataset split defined by the authors, we use all the clips from 26 matches as a training set and the remaining 3 matches as a testing set.
Table 1: Summary of 5 SBDT datasets used in our evaluation. Among them, Volleyball and Basketball are newly introduced in this work. Also, for Soccer and Basketball we provide novel frame-wise manual annotations of 2D ball position. In this table, "resolution" represents the majority of image resolution in the dataset and "disp." represents the average ball displacement in pixel between consecutive frames. Notice that frame per second (FPS) of Volleyball and Basketball are unknown (i.e., N/A), since they are not provided by adapted image sequences.
Basketball. This dataset is also introduced for the first time in the SBDT literature. We adapt the video clips provided by [91], but there is no public ball annotations for this. Therefore, we manually annotated ball positions to 45% (81/181 games) of the whole video clips, resulting in 275,328 annotated images composed of 3,824 video clips. Currently, this is the largest SBDT dataset. Notice that the average ball displacement between consecutive frames is the largest among the five datasets (cf. Table 1). Also, camera frequently moves and zooms in rapidly to follow where play happens, which causes a complex ball trajectory in a video.
Most existing SBDT implementations have not been made public. While a few exceptions exist78, unfortunately they are strongly tied up with particular datasets, thus difficult to be applied to others. Therefore, here we re-implement state-of-the-art SBDT methods to perform comparison on various SBDT datasets. In particular, we implemented DeepBall [40, 42], BallSeg [80], TrackNetV2 [75] and MonoTrack [50]. For DeepBall, since its original model is very small (< 0.1M parameters), we built a variant by simply increasing intermediate feature dimension, which is called DeepBall-Large in the followings. Also, we deployed an unpublished variant9 of TrackNetV2, where residual connection and transposed convolution are additionally employed. We call this variant as ResTrackNetV2.
We report the performances of our SOTA re-implementations in Table 2. It shows that the accuracy of our TrackNetV2 [75] implementation on the Badminton dataset is 85.6, while Table IV in [75] shows that the original implementation scores 85.2, which indicates the
7https://nol.cs.nctu.edu.tw:234/open-source/TrackNetv2 8https://nol.cs.nctu.edu.tw:234/open-source/TrackNet 9https://github.com/Chang-Chia-Chi/TrackNet-Badminton-Tracking-tensorflow2
DeepBall [40, 41] DeepBall-Large BallSeg [80] TrackNetV2 [75] ResTrackNetV2 MonoTrack [50]
Badminton
F1  Acc.  AP  FPS  F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS
Table 2: Benchmark results of SBDT methods on 5 SBDT datasets. We set the distance threshold  = 4 [pixel] to compute F1, Accuracy (Acc.) and Average Precision (AP), all of which are shown as percentages. Red values are the best while green values are the secondbest among all the methods. Blue values are the best in existing methods.
We evaluate SBDT models using F1, Accuracy (Acc.) and Average Precision (AP). With a distance threshold  [pixel], for each frame we calculate the distance between a predicted ball position and a ground truth to classify the prediction into true positive, true negative, false positive or false negative. F1 and Acc. can be directly computed with the results, while AP is computed over all the positive results with prediction confidences.
F1
Badminton
TrackNetV2
ResTrackNetV2
MonoTrack
Figure 6: F1 (first row), Accuracy (second row) and Average Precision (third row) of SBDT methods with different distance threshold  [pixel] on 5 SBDT datasets.
Figure 6 shows F1, Accuracy and AP scores of SBDT methods with different distance thresholds. Interestingly, the performances of DeepBall [40, 42] and BallSeg [80] heavily depend on the dataset, while TrackNetV2 [75], ResTrackNetV2 and MonoTrack [50] stably yield good results through the datasets. Compared to these methods, WASB consistently achieves higher performance with most of the threshold settings on all the sports categories, which indicates the wide-applicability of our approach.
Badminton
F1  Acc.  AP  FPS  F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS
Badminton
F1  Acc.  AP  F1 Acc. AP F1 Acc. AP
[9] Bingqi Chen and Zhiqiang Wang. A Statistical Method for Analysis of Technical Data of a Badminton Match Based on 2-D Seriate Images. Tsinghua Science and Technology, 2007.
[13] Wei Chen and Yu-Jin Zhang. Tracking Ball and Players with Applications to Highlight Ranking of Broadcasting Table Tennis Video. In The Proceedings of the Multiconference on "Computational Engineering in Systems Applications", 2006.
[50] Paul Liu and Jui-Hsien Wang. MonoTrack: Shuttle Trajectory Reconstruction From Monocular Badminton Video. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops, 2022.
[58] Hnin Myint, Patrick Wong, Laurence Dooley, and Adrian Hopgood. Tracking a Table Tennis Ball for Umpiring Purposes. In 2015 14th IAPR International Conference on Machine Vision Applications (MVA), 2015.
[81] Roman Voeikov, Nikolay Falaleev, and Ruslan Baikulov. TTNet: Real-Time Temporal and Spatial Video Analysis of Table Tennis. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops, June 2020.
[83] Wei-Yao Wang, Hong-Han Shuai, Kai-Shiang Chang, and Wen-Chih Peng. ShuttleNet: Position-Aware Fusion of Rally Progress and Player Styles for Stroke Forecasting in Badminton. Proceedings of the AAAI Conference on Artificial Intelligence, 2022.
[86] Kam Cheung Patrik Wong and Laurence S. Dooley. High-motion Table Tennis Ball Tracking for Umpiring Applications. In IEEE 10th INTERNATIONAL CONFERENCE ON SIGNAL PROCESSING PROCEEDINGS, 2010.
[92] Changqian Yu, Bin Xiao, Changxin Gao, Lu Yuan, Lei Zhang, Nong Sang, and Jingdong Wang. Lite-HRNet: A Lightweight High-Resolution Network. In 2021 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2021.
[106] Zhengtao Zhang, De Xu, and Min Tan. Visual Measurement and Prediction of Ball Trajectory for Table Tennis Robot. IEEE Transactions on Instrumentation and Measurement, 2010.
Binary file (standard input) matches

### 29. user (2026-07-06T19:37:07.208Z)

Web search results for query: "TrackNetV2 original repository GitLab nol_cs Chih-Chuan Sun shuttlecock dataset download license"

Links: [{"title":"GitHub - ChgygLin/TrackNetV2-pytorch: A Pytorch implementation of TrackNetV2 from Tensorflow (ncnn c++ inference) · GitHub","url":"https://github.com/ChgygLin/TrackNetV2-pytorch"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network - National Yang Ming Chiao Tung University Academic Hub","url":"https://scholar.nycu.edu.tw/en/publications/tracknetv2-efficient-shuttlecock-tracking-network/"},{"title":"GitHub - qaz812345/TrackNetV3: Implementation of paper - TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification · GitHub","url":"https://github.com/qaz812345/TrackNetV3"},{"title":"Shuttlecock Trajectory Dataset - HackMD","url":"https://hackmd.io/@TUIK/rJkRW54cU"},{"title":"TrackNetV5: Residual-Driven Spatio-Temporal Refinement and Motion Direction Decoupling for Fast Object Tracking","url":"https://arxiv.org/pdf/2512.02789"},{"title":"BFMD: A Full-Match Badminton Dense Dataset for Dense Shot Captioning","url":"https://arxiv.org/pdf/2603.25533"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Papers | HyperAI","url":"https://beta.hyper.ai/en/papers/tracknetv2-efficient-shuttlecock-tracking"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Request PDF","url":"https://www.researchgate.net/publication/350935356_TrackNetV2_Efficient_Shuttlecock_Tracking_Network"},{"title":"open-source / TrackNetV2 · GitLab","url":"https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2"},{"title":"TrackNetV2: Efficient Shuttlecock Tracking Network | Semantic Scholar","url":"https://www.semanticscholar.org/paper/TrackNetV2:-Efficient-Shuttlecock-Tracking-Network-Sun-Lin/223c287d516284fec9bd9792ca2805aa0f551fc9"}]

Based on the search results, here's what I found about TrackNetV2:

## Original Repository and Location

The dataset and source code are available at https://nol.cs.nctu.edu.tw:234/open-source/TrackNetv2/. The original repository is hosted on GitLab Community Edition at https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2.

## Authors

The work was authored by Sun, Nien En; Lin, Yu Ching; Chuang, Shao Ping; Hsu, Tzu Han; Yu, Dung Ru; Chung, Ho Yi; and Ik, Tsì-Uí.

## Shuttlecock Dataset

The dataset can be downloaded including professional matches and amateur games at https://nycu1-my.sharepoint.com/:u:/g/personal/tik_m365_nycu_edu_tw/EWisYhAiai9Ju7L-tQp0ykEBZJd9VQkKqsFrjcqqYIDP-g?e=S0AB1Z. The dataset was created for the model training and testing of TrackNet and TrackNetV2 for badminton applications.

The dataset details include: The dataset is composed of 26 broadcast videos with a resolution and frame rate of 1280×720 and 30 fps, respectively.

## License Information

Unfortunately, the search results did not contain specific information about the license under which TrackNetV2 and its dataset are distributed.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 30. assistant (2026-07-06T19:37:11.708Z)

Excellent — I now have the WASB paper's key facts: the badminton benchmark **is** the TrackNetV2 dataset, and WASB compares against TrackNetV2/ResTrackNetV2/MonoTrack. I need the exact F1/Acc/AP numbers for WASB vs others on badminton. The PDF text extraction showed the table structure but not the numeric cells (they're in a separate column layout). Let me extract the full page text to get Table 2 numbers, and check the TrackNetV2 GitLab license + a YOLO shuttlecock search.

### 31. user (2026-07-06T19:37:17.614Z)

=== Full text page-by-page, looking for Table 2 numeric block ===
sports such as badminton [83], baseball [74], basketball [24], golf [30], soccer [72, 78],
tennis [64], table tennis [18], and volleyball [15]. Several commercial systems like Hawk-
Eye1 and KINEXON2 have already been successfully introduced to professional leagues, but
they usually require high-cost installation. Computer vision techniques can be an alternative
approach to obtain ball trajectories from easily available video data. However, this Sports
Ball Detection and Tracking (SBDT) task is challenging due to the small size of a sports ball,
its high speed, occlusion, blending in with surroundings, and camera motion [96].

    This SBDT task can uniformly be defined through various ball-games. Therefore, wide
applicability is an important property to be equipped by good SBDT methods. However,

--
Figure 1: Exemplar ball trajectories extracted from soccer, tennis, badminton, volleyball and
basketball videos, respectively. Best viewed in color.

while there are extensive literatures of SBDT methods proposed in the last two decades,
most of them cannot be directly applied to different domains, since they are tailor-made for
specific sports (e.g., badminton [9], baseball [74], basketball [5, 6, 7, 8, 11], golf [53, 54],
soccer [3, 4, 16, 17, 19, 20, 21, 31, 34, 36, 46, 47, 48, 52, 55, 56, 57, 60, 61, 62, 66, 67,
68, 73, 79, 93, 94, 95, 96, 98, 99, 100, 102, 111, 112], tennis [1, 2, 22, 28, 29, 38, 39, 43,
59, 64, 69, 77, 85, 86, 88, 89, 90, 97, 101, 103, 109, 110], table tennis [13, 18, 23, 26, 58,
104, 105, 106], volleyball [10, 12, 14, 15]). Recent approaches [32, 40, 42, 50, 75, 80] based
on Convolutional Neural Networks (CNNs) can potentially be used for different ball-games,
but unfortunately in their works evaluations are limited to almost one sports category.

    Here we aim at building a new state-of-the-art (SOTA) SBDT method widely applicable
to various sports categories. To achieve this goal, we will make the following contributions:

--
       category, we use 5 datasets from different sports categories (i.e., badminton, basket-
       ball, soccer, tennis, volleyball) to compare our approach with 6 SOTA SBDT methods
       [40, 50, 75, 80]. We establish this experimental protocol by introducing two novel
       datasets, providing new manual annotations for two datasets, and re-implementing all
       the existing methods. Experimental results demonstrate that our method substantially
       outperforms all the SBDT methods on all the datasets used in our evaluation.

These contributions indicate that our proposed approach can play as a Widely Applicable
Strong Baseline (WASB) of SBDT. Also, we make datasets and codebases publicly available,
which we believe promotes future SBDT research.

2 Related Work

Roughly speaking, classical SBDT methods [2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 18, 23, 31, 36,
38, 43, 47, 53, 54, 57, 62, 66, 73, 77, 79, 86, 88, 89, 90, 93, 94, 95, 96, 97, 100, 101, 102,
104, 109, 110, 111, 112] are based on tracking-by-detection paradigm: Ball candidates are
first detected from each video frame, then a true trajectory is recovered by associating the
candidates through time. The most typical ball candidate detector is a temporal background
subtraction. However, this approach can easily be contaminated by non-ball moving objects
like players, even though it requires careful tuning to the target domain.

    Recent methods [25, 32, 35, 40, 41, 42, 50, 70, 75, 80, 81, 87] significantly ameliorate the
above issue by employing encoder-decoder CNN models. For example, DeepBall [40, 41]
TARASHIMA ET AL.: WIDELY APPLICABLE STRONG BASELINE FOR SBDT                           3

is composed of a variant of fully convolutional networks [51], in which intermediate multi-
scale features are fused in a decoder to extract high-resolution heatmaps representing ball
positions. BallSeg [80] is a modification of ICNet [108], so that two consecutive frames can
be fed into the model to capture ball dynamics. TrackNet and its variants [32, 50, 75] are
based on U-Net [71] architecture, following a multiple-in multiple-out (MIMO) design to
efficiently capture ball movement. Usually, training these models inevitably confronts high
foreground-background class imbalance, due to the small ball size appeared in sports videos.
Existing methods address this issue by adapting the focal loss 3 [49], the combo loss [76] or
hard negative mining technique [51]. Notice that in these recent methods, ball dynamics are
considered only within frames that are combined in the same batch.

    We argue that, in recent methods described above, there is room for improvement with
respect to (1) high-resolution feature extraction, (2) model training being aware of tiny ball
position, and (3) inference which takes temporal consistency of ball position into account.
In the next section, we introduce solutions to improve these potential drawbacks.

--
Badminton [75]. This dataset was introduced by the TrackNetV2 work [75]. Following the
dataset split defined by the authors, we use all the clips from 26 matches as a training set and
the remaining 3 matches as a testing set.

    6https://pspagnolo.jimdofree.com/download/
TARASHIMA ET AL.: WIDELY APPLICABLE STRONG BASELINE FOR SBDT                          7

                               Train                     Test

             resolution FPS games clips frames disp.[pixel] games clips frames disp.

--
--
accuracy of our TrackNetV2 [75] implementation on the Badminton dataset is 85.6, while
Table IV in [75] shows that the original implementation scores 85.2, which indicates the

    7https://nol.cs.nctu.edu.tw:234/open-source/TrackNetv2
    8https://nol.cs.nctu.edu.tw:234/open-source/TrackNet
    9https://github.com/Chang-Chia-Chi/TrackNet-Badminton-Tracking-tensorflow2
8                    TARASHIMA ET AL.: WIDELY APPLICABLE STRONG BASELINE FOR SBDT

                               Soccer  Tennis  Badminton  Volleyball  Basketball

                     # param.  F1  Acc.  AP  FPS  F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS F1 Acc. AP FPS

DeepBall [40, 41]      0.1M    44.5 92.7 26.3 44.6 47.4 32.3 47.0 52.1 52.4 38.6 60.0 57.1 64.4 50.7 49.2 21.1 0.0 12.9 0.0 30.3
DeepBall-Large         1.0M    44.9 89.5 34.0 42.0 46.7 31.6 35.1 47.7 50.6 36.8 59.5 53.0 70.4 57.5 56.5 21.1 57.2 47.5 36.6 30.9
BallSeg [80]          12.7M    36.1 92.6 20.0 64.8 71.7 57.5 56.8 62.7 79.9 72.2 68.4 75.0 19.5 17.5 8.5 18.2 16.8 20.5 5.3 29.5
TrackNetV2 [75]       11.3M    86.6 97.7 77.2 66.0 89.4 81.4 80.6 55.3 90.5 85.6 83.6 77.0 83.6 73.8 72.3 17.6 78.8 69.3 64.6 28.0
ResTrackNetV2          1.2M    84.6 97.4 75.5 56.2 90.3 82.8 81.7 59.0 89.4 84.0 82.2 71.3 84.2 74.7 74.7 28.6 77.9 68.2 66.0 38.2
MonoTrack [50]         2.9M    85.2 97.4 78.6 58.0 92.1 85.9 87.3 64.1 90.9 85.9 84.9 75.5 85.1 75.9 72.1 19.7 80.8 71.3 65.3 32.1

WASB (Ours, Step=3)    1.5M    88.3 97.9 83.6 55.7 94.0 89.0 91.0 58.2 91.6 87.0 88.5 70.4 86.5 77.9 79.9 18.0 80.6 71.3 71.5 30.2
WASB (Ours, Step=1)    1.5M    88.2 97.9 86.2 23.6 95.6 91.8 94.2 35.2 93.1 89.0 91.6 34.3 88.0 80.0 83.2 15.8 82.6 73.4 77.1 22.3

Table 2: Benchmark results of SBDT methods on 5 SBDT datasets. We set the distance
threshold  = 4 [pixel] to compute F1, Accuracy (Acc.) and Average Precision (AP), all of
which are shown as percentages. Red values are the best while green values are the second-
best among all the methods. Blue values are the best in existing methods.

correctness (or, superiority) of our TrackNetV2 implementation. Unfortunately, such a vali-
dation cannot be performed for the remaining five methods: The original DeepBall [41] was
--
                                          Soccer                   Tennis          Badminton                 Volleyball          Basketball

                        100     DeepBall                100                   100                 100
                                DeepBall-Large
                                BallSeg                                                                                     80

### 32. user (2026-07-06T19:37:26.977Z)

Web search results for query: "YOLOv8 shuttlecock detection badminton model roboflow accuracy small fast object tracking"

Links: [{"title":"MATCHMOTION: AN AI-POWERED MOBILE APPLICATION FOR AUTOMATED BADMINTON VIDEO ANALYSIS USING YOLOV8 OBJECT DETECTION","url":"https://www.researchgate.net/publication/404597971_MATCHMOTION_AN_AI-POWERED_MOBILE_APPLICATION_FOR_AUTOMATED_BADMINTON_VIDEO_ANALYSIS_USING_YOLOV8_OBJECT_DETECTION"},{"title":"Detecting the shuttlecock for a badminton robot: A YOLO based approach | Request PDF","url":"https://www.researchgate.net/publication/343521001_Detecting_the_shuttlecock_for_a_badminton_robot_A_YOLO_based_approach"},{"title":"Top Shuttlecock Datasets and Models | Roboflow Universe","url":"https://universe.roboflow.com/search?q=class:shuttlecock"},{"title":"One-Shot Badminton Shuttle Detection for Mobile Robots","url":"https://arxiv.org/html/2603.06691v2"},{"title":"Automated Service Height Fault Detection Using Computer Vision and Machine Learning for Badminton Matches","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10747833/"},{"title":"A New Perspective for Shuttlecock Hitting Event Detection","url":"https://arxiv.org/pdf/2306.10293"},{"title":"Enhancing Badminton Game Analysis: An Approach to Shot Refinement via a Fusion of Shuttlecock Tracking and Hit Detection from Monocular Camera","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11244353/"},{"title":"GitHub - muhammadyasin79/Badminton_Analytics_Project: Real‑time badminton analytics using YOLOv8‑Pose - skeleton overlay, player stats and trajectory visualisation with OpenCV & MoviePy.","url":"https://github.com/muhammadyasin79/Badminton_Analytics_Project"},{"title":"Detecting the shuttlecock for a badminton robot: A YOLO based approach - ScienceDirect","url":"https://www.sciencedirect.com/science/article/abs/pii/S0957417420306436"}]

I found comprehensive information about YOLOv8 shuttlecock detection models for badminton. Here are the key findings:

## Detection Accuracy

A fine-tuned YOLOv8 network optimized for real-time shuttlecock detection achieved an F1-score of 0.86 under controlled test environments similar to training, and 0.70 in entirely unseen environments. However, experimental evaluations on BWF World Championship rally videos yielded a mean shuttle detection accuracy of 37.6% and a mean hit recognition accuracy of 81.7%.

## Real-Time Performance

YOLOv8 networks have been specifically optimized for real-time shuttlecock detection. This makes them suitable for fast object tracking applications in badminton.

## Small Object Detection Challenges

Detection performance is critically dependent on shuttlecock size and background texture complexity. To address YOLO's limitations with small objects like shuttlecocks, researchers have combined multiple approaches—TrackNetV2 has been incorporated to compensate for the shortcomings of YOLO in detecting badminton, as there may still arise scenarios where both YOLOv5m and TrackNetV2 fail to detect the shuttlecock simultaneously.

## Roboflow Integration

Roboflow Universe hosts multiple shuttlecock detection datasets and models, including YOLOv8-based projects with varying numbers of images and trained models. Additionally, a YOLO11 object detection model is custom-trained to detect the shuttlecock using training data sourced from an open-source Roboflow dataset.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 33. assistant (2026-07-06T19:37:31.704Z)

I now have the complete WASB Table 2 badminton numbers. This is the key comparative data. Let me confirm the TrackNetV2 GitLab license (the original repo/dataset provenance — this is the crux of the commercial-use question, since all these trackers train on that badminton dataset) and confirm Ultralytics AGPL. Let me also verify the WASB architecture backbone (HRNet — already confirmed) and check the original TrackNetV2 repo for a license.

### 34. user (2026-07-06T19:37:37.528Z)

Based on the web page content provided, I cannot answer your questions about:

- **LICENSE file or stated license** – Not visible in the excerpt
- **Dataset usage terms** – Not mentioned in the excerpt
- **Commercial use permissions** – Not specified in the excerpt
- **Framework/version** – Not indicated in the excerpt

The page shows only project metadata (29 commits, 1 branch, creation date of March 25, 2020) and a README link, but the actual content of those files isn't included in your excerpt. To find this information, you would need to:

1. Check the repository's LICENSE file directly
2. Review the README.md file
3. Look for dataset documentation or terms of use statements in the repository

I recommend visiting the GitLab repository directly to access these details.

### 35. user (2026-07-06T19:37:40.735Z)

# Dataset Source and Licensing Information

## Dataset Link
The verbatim reference states: "Download [Shuttlecock Trajectory Dataset](https://hackmd.io/Nf8Rh1NrSrqNUzmO0sQKZw)"

The dataset is hosted on HackMD at that URL. However, the webpage provided does not explicitly state any license terms or commercial-use restrictions for the dataset itself.

## Recent Activity
The most recent visible commit information shows "36 Commits" in the repository's history, but no specific commit date is displayed in the extracted content. The repository shows 270 stars and 64 forks, indicating active community interest.

## License Status
The TrackNetV3 repository itself carries an "MIT license," which permits commercial use. However, **no license information for the Shuttlecock Trajectory Dataset is mentioned** in this GitHub page. You would need to check the HackMD link directly for dataset-specific licensing terms.

### 36. user (2026-07-06T19:37:43.407Z)

Web search results for query: "Ultralytics YOLOv8 YOLO11 license AGPL-3.0 commercial enterprise license"

Links: [{"title":"Ultralytics License","url":"https://www.ultralytics.com/license"},{"title":"Ultralytics","url":"https://roboflow.com/ultralytics"},{"title":"YOLOv11 AGPL License for On-Premises Use - Discussion - Ultralytics","url":"https://community.ultralytics.com/t/yolov11-agpl-license-for-on-premises-use/1529"},{"title":"YOLO Object Detection & Segmentation | Ultralytics Docs","url":"https://docs.ultralytics.com/"},{"title":"Ultralytics YOLO License Information","url":"https://developer.imagimob.com/legal/ultralytics-license-information"},{"title":"YOLO Model Licenses: A Developer’s Guide | by Bing Bai | Medium","url":"https://medium.com/@bingbai.jp/yolo-model-licenses-a-developers-guide-da722767b6f8"},{"title":"After training the yolo model, if it is to be commercialized, is it necessary to pay for it - Support - Ultralytics","url":"https://community.ultralytics.com/t/after-training-the-yolo-model-if-it-is-to-be-commercialized-is-it-necessary-to-pay-for-it/1193"},{"title":"A question about the license · ultralytics · Discussion #1260","url":"https://github.com/orgs/ultralytics/discussions/1260"}]

Based on the search results, here's what I found about Ultralytics YOLOv8/YOLO11 licensing:

## License Overview

YOLOv8 and YOLOv11 are distributed under AGPL-3.0 license. All Ultralytics YOLO trained models fall under the AGPL-3.0 License by default, which covers the training code and the models produced by that training code.

## AGPL-3.0 Requirements

AGPL-3.0 requires the user to open-source any code changes they make (including the code of any other projects that connect directly to the model). More specifically, compliance means publicly releasing the complete corresponding source code for the entire derivative work, including the larger application, modifications, scripts, configuration files, and, where applicable, model weights.

## Enterprise License Alternative

An Enterprise License provides organizations with the ability to modify Ultralytics YOLO source code and embed Ultralytics YOLO code and models in commercial products without needing to follow the constraints of the AGPL-3.0 License, namely the requirement to open-source modified works or larger works containing Ultralytics YOLO code and models.

A separate Enterprise License is not required for each Ultralytics product—with this license, you will have access to the complete Ultralytics YOLO source code portfolio, including YOLO26, earlier YOLO versions, and any future YOLO models that Ultralytics may release during the license term.

## Who Needs Which License

The AGPL-3.0 License is ideal for educational and non-commercial use, promoting open collaboration, while the Enterprise License is for development and production use, including internal tools, automated workflows, and production deployments, bypassing the open-source requirements of AGPL-3.0.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 37. assistant (2026-07-06T19:37:46.896Z)

Let me get the definitive answer on the badminton dataset commercial-use terms — this is the single most load-bearing open question, since all these trackers train on the same TrackNetV2 Shuttlecock dataset. Let me fetch the dataset HackMD page and the TrackNetV2 GitLab README raw.

### 38. user (2026-07-06T19:37:54.714Z)

# Shuttlecock Trajectory Dataset - License & Usage Analysis

## License & Terms of Use
**No explicit license, copyright notice, or usage restrictions are stated** on this HackMD page. The document contains no verbatim license text, terms of service specific to the dataset, or commercial-use restrictions.

## Dataset Provider
The dataset is provided by researchers at National Yang Ming Chiao Tung University (NYCU), with contributors listed as 林育慶、孫念恩、and Tsì-Uí İk. It's hosted via SharePoint at `nycu1-my.sharepoint.com`.

## Dataset Specifications
- **Total frames**: 78,200 across 26 broadcast videos
- **Resolution/Frame rate**: 1280×720, 30 fps
- **Composition**: 23 professional matches (68,675 frames) + 3 amateur games (9,525 frames)
- **Content**: Rally-based badminton footage with labeled shuttlecock trajectory data

## Purpose
The dataset was explicitly created for "model training and testing of TrackNet and TrackNetV2 for badminton applications."

## Recommendation
Contact the dataset creators directly regarding permitted uses, as no formal license statement appears in the provided documentation.

### 39. user (2026-07-06T19:37:57.248Z)

=== TrackNetV2 GitLab README (raw attempts) ===
--- https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2/-/raw/master/README.md ---
You can predict coordinate of shuttlecock for a single video with:
- The details of our dataset: https://hackmd.io/Nf8Rh1NrSrqNUzmO0sQKZw
Unrar dataset and apply

--- https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2/-/raw/main/README.md ---

--- https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2/-/raw/master/LICENSE ---

### 40. assistant (2026-07-06T19:38:04.676Z)

I now have all the key facts confirmed. The critical finding is clear: the TrackNetV2 badminton dataset (used by ALL these trackers as their benchmark/training data) has **no stated license** — a major commercial-use open question. Let me do two quick final confirmations: the WASB architecture/backbone details are confirmed (HRNet). Let me verify the alenzenx TrackNetV3 recency and check if there's a newer WASB successor (the search surfaced "TrackNetV5" arXiv 2512 — worth a quick note for option E).

### 41. user (2026-07-06T19:38:11.216Z)

=== alenzenx/TrackNetV3 repo meta ===
  "updated_at": "2026-07-06T08:58:28Z",
  "pushed_at": "2025-06-02T12:26:32Z",
  "stargazers_count": 158,
  "archived": false,
  "license": {
    "spdx_id": "MIT",
=== qaz812345/TrackNetV3 repo meta ===
  "updated_at": "2026-07-06T05:38:00Z",
  "pushed_at": "2025-04-15T15:13:35Z",
  "stargazers_count": 270,
  "license": {
    "spdx_id": "MIT",
=== alenzenx LICENSE check ===
--- LICENSE ---
MIT License

Copyright (c) 2024 alenzenx

--- LICENSE.md ---
404: Not Found

### 42. user (2026-07-06T19:38:17.632Z)

Web search results for query: "WASB successor sports ball tracking 2024 2025 improved shuttlecock HRNet license MIT arXiv"

Links: [{"title":"TrackNetV3: Enhancing ShuttleCock Tracking with Augmentations and Trajectory Rectification | Request PDF","url":"https://www.researchgate.net/publication/377061399_TrackNetV3_Enhancing_ShuttleCock_Tracking_with_Augmentations_and_Trajectory_Rectification"},{"title":"(PDF) Widely Applicable Strong Baseline for Sports Ball Detection and Tracking","url":"https://www.researchgate.net/publication/376208967_Widely_Applicable_Strong_Baseline_for_Sports_Ball_Detection_and_Tracking"},{"title":"High Speed and Tiny Objects Tracking System in Racquet Sports Videos Using Deep Learning with Trajectory Rectification Feature - ScienceDirect","url":"https://www.sciencedirect.com/science/article/pii/S1877050925016709"},{"title":"BFMD: A Full-Match Badminton Dense Dataset for Dense Shot Captioning","url":"https://arxiv.org/pdf/2603.25533"},{"title":"(PDF) BlurBall: Joint Ball and Motion Blur Estimation for Table Tennis Ball Tracking","url":"https://www.researchgate.net/publication/395771245_BlurBall_Joint_Ball_and_Motion_Blur_Estimation_for_Table_Tennis_Ball_Tracking"},{"title":"TrackNetV5: Residual-Driven Spatio-Temporal Refinement and Motion Direction Decoupling for Fast Object Tracking","url":"https://arxiv.org/pdf/2512.02789"},{"title":"Widely Applicable Strong Baseline for Sports Ball ...","url":"https://papers.bmvc2023.org/0310.pdf"},{"title":"MonoTrack: Shuttle trajectory reconstruction from monocular badminton   video","url":"https://arxiv.org/pdf/2204.01899"},{"title":"Sports Ball Detection And Tracking","url":"https://www.catalyzex.com/s/Sports%20Ball%20Detection%20And%20Tracking"}]

Based on the search results, I found relevant information about WASB and its successors in sports ball tracking:

The Widely Applicable Strong Baseline (WASB) switched from a U-Net to an HRNet backbone for improved results.

Several successors to WASB have been developed:

1. **TrackNetV3**: TrackNetV3: Enhancing shuttlecock tracking with augmentations and trajectory rectification was published in the Proceedings of the 5th ACM International Conference on Multimedia in Asia in 2023.

2. **TrackNetV4**: TrackNetV4 fuses high-level visual features with learnable motion attention maps through a motion-aware fusion mechanism, and experimental results on tennis ball and shuttlecock datasets show it enhances the tracking performance of both TrackNetV2 and V3, serving as a lightweight, plug-and-play solution built on top of the existing TrackNet.

3. **TrackNetV5**: TrackNetV5: Residual-Driven Spatio-Temporal Refinement and Motion Direction Decoupling for Fast Object Tracking is a recent preprint from 2024.

4. **BlurBall**: BlurBall is a model based on HRNet with SE attention mechanism trained for joint ball detection and blur estimation.

However, I did not find specific information about MIT licenses or detailed arXiv references in these results. You may want to search directly on arXiv for more specific licensing and publication details.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 43. assistant (2026-07-06T19:39:25.883Z)

I have comprehensive, sourced facts across all options. I have enough to write the report. Let me compile the findings.

---

# Shuttlecock/ball trackers vs WASB-SBDT — falsifiable facts (as of mid-2026)

**Baseline reference (WASB-SBDT):** NTT Communications' BMVC 2023 model. License **MIT, Copyright (c) 2023 NTT Communications Corporation** (confirmed from the actual `LICENSE.md`, not just a badge). Architecture is a **small-HRNet** high-resolution heatmap network + position-aware training + temporal-consistency inference. Its badminton benchmark **is the TrackNetV2 Shuttlecock dataset** (26-match train / 3-match test split). WASB reports the best badminton numbers in its own Table 2 (below). The dataset provenance caveat below applies to WASB too, since it trains on the same NYCU data.

The single most important cross-cutting open question: **every one of these trackers benchmarks and trains on the NYCU/TrackNetV2 "Shuttlecock Trajectory Dataset," which has no stated license** — see the end.

---

## A. TrackNetV2 (NYCU / CoachAI lineage)

- **Architecture:** U-Net-style encoder-decoder with a **VGG16-based encoder** + upsampling decoder with skip connections; **heatmap** output. Multi-frame **MIMO** (multiple-in-multiple-out) design; 3 consecutive frames in, heatmaps out. Heatmap changed to a real-valued 2D array; loss is weighted cross-entropy. ~11.3M params (per WASB Table 2). — [scholar.nycu.edu.tw](https://scholar.nycu.edu.tw/en/publications/tracknetv2-efficient-shuttlecock-tracking-network/), [WASB paper §Related Work + Table 2](https://papers.bmvc2023.org/0310.pdf)
- **Framework:** TensorFlow/Keras (original GitLab repo, created 2020-03-25). Older, non-PyTorch. A community PyTorch port exists ([ChgygLin/TrackNetV2-pytorch](https://github.com/ChgygLin/TrackNetV2-pytorch)). — [gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2](https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2)
- **Dataset introduced:** The "Shuttlecock Trajectory Dataset" — 26 broadcast videos, 1280×720@30fps, **78,200 frames** = 23 professional matches (68,675 frames) + 3 amateur games (9,525 frames). — [dataset HackMD](https://hackmd.io/Nf8Rh1NrSrqNUzmO0sQKZw)
- **Accuracy (authors' own):** 85.2% accuracy on a brand-new match test; **F1 97.03%** on the Shuttlecock Trajectory Dataset (authors' figure). In WASB's independent re-implementation on badminton (dist. threshold 4px): **F1 90.5, Acc 85.6, AP 83.6**. — [NYCU pub](https://scholar.nycu.edu.tw/en/publications/tracknetv2-efficient-shuttlecock-tracking-network/), [WASB Table 2](https://papers.bmvc2023.org/0310.pdf)
- **License:** **Open question / likely problematic.** The original GitLab repo has **no LICENSE file** (raw `LICENSE` fetch returned empty; README only links to the dataset). No commercial-use grant is stated anywhere. — [GitLab repo](https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2)
- **Weights provenance:** NTT redistributes a TrackNetV2 badminton checkpoint (their re-implementation) in the WASB Model Zoo under NTT's MIT terms — [MODEL_ZOO.md](https://github.com/nttcom/WASB-SBDT/blob/main/MODEL_ZOO.md). Original NYCU weights come with no license.

## B. TrackNetV3

Two distinct repos share the name — keep them separate:

**B1. qaz812345/TrackNetV3** (the one matching the "augmentations + rectification" MMAsia 2023 paper)
- **Architecture:** Two modules — (1) **trajectory prediction** using an estimated background as auxiliary input + mixup augmentation; (2) **rectification** that builds repair masks from the predicted trajectory and **inpaints** gaps. — [paper](https://people.cs.nycu.edu.tw/~yushuen/data/TrackNetV3.pdf), [dl.acm.org/10.1145/3595916.3626370](https://dl.acm.org/doi/10.1145/3595916.3626370)
- **Accuracy:** Paper reports raising accuracy from **87.72% → 97.51%** over prior standard methods; repo table shows **TrackNetV3 Acc 97.51 / F1 98.56 vs TrackNetV2 Acc 94.98 / F1 97.03**. Note these are the authors' own numbers, not WASB's harness, so **not directly comparable** to WASB's Table 2 (different eval protocol). — [github.com/qaz812345/TrackNetV3](https://github.com/qaz812345/TrackNetV3)
- **License:** **MIT, Copyright (c) 2024 qaz812345** (confirmed from `LICENSE` file). — [LICENSE](https://github.com/qaz812345/TrackNetV3/blob/master/LICENSE)
- **Framework/recency:** Python 3.8.7, **PyTorch 1.10.0**; modern-ish. Actively maintained-ish: last push **2025-04-15**, 270 stars.
- **Weights:** Public Google Drive (`TrackNet_best.pt`, `InpaintNet_best.pt`). Trained on the **"Shuttlecock Trajectory Dataset"** (linked to HackMD — the NYCU dataset). **Open question:** dataset carries no license (see below).

**B2. alenzenx/TrackNetV3** (the repo you named)
- **Architecture:** Described as a semantic-segmentation tracking net, self-described as "the first TrackNet using Attention." Different lineage from B1. — [github.com/alenzenx/TrackNetV3](https://github.com/alenzenx/TrackNetV3)
- **Accuracy (authors' own):** **90.53% vs TrackNetV2 88.49%** on their split (train 32,421 / val 3,717 / test 11,118 images). Numbers are lower than B1 and again not WASB-protocol.
- **License:** **MIT, Copyright (c) 2024 alenzenx** (confirmed). — [LICENSE](https://github.com/alenzenx/TrackNetV3)
- **Framework/recency:** PyTorch (CUDA 11.7 install), Python 3.7.9–3.9.4. Last push **2025-06-02**, 158 stars, not archived — the more recently touched of the two.
- **Weights/dataset:** Google Drive weights (90.53%); trained on badminton frames; dataset license not stated → same open question.

## C. MonoTrack (CVPRW 2022)

- **What it does:** First end-to-end system to reconstruct **3D shuttle trajectories from monocular badminton video**, integrating court detection, player **pose** (via MMPose/MMDet), shuttle tracking, and physics/domain priors; also improved SOTA on court recognition, 2D trajectory, and hit recognition. — [arXiv:2204.01899](https://arxiv.org/abs/2204.01899), [CVF open access](https://openaccess.thecvf.com/content/CVPR2022W/CVSports/html/Liu_MonoTrack_Shuttle_Trajectory_Reconstruction_From_Monocular_Badminton_Video_CVPRW_2022_paper.html)
- **Tracker component:** A **modified TrackNet** (heatmap CNN); ~2.9M params in WASB's re-impl. In WASB Table 2 on badminton it scores **F1 90.9, Acc 85.9, AP 84.9** — marginally above TrackNetV2, below WASB. — [github.com/jhwang7628/monotrack](https://github.com/jhwang7628/monotrack), [WASB Table 2](https://papers.bmvc2023.org/0310.pdf)
- **License:** **BLOCKER for commercial use.** The repo's `LICENSE` is the **Adobe Research License — noncommercial research/teaching only** ("The rights granted herein may be exercised for noncommercial research purposes … only. Noncommercial research purposes do not include commercial licensing or distribution, development of commercial products…"). GitHub classifies it as `NOASSERTION`/"Other." Repo last pushed 2023-07-27 (not actively maintained). — [monotrack LICENSE](https://github.com/jhwang7628/monotrack/blob/master/LICENSE)

## D. YOLO-based shuttlecock detection (YOLOv8 / YOLO11)

- **Feasibility/accuracy:** Works but weak on the tiny, fast, motion-blurred shuttle. Published fine-tuned YOLOv8: **F1 0.86** in-domain, **0.70** in unseen environments, and **only 37.6% mean shuttle detection accuracy on BWF World Championship rallies** — i.e., far below TrackNet/WASB heatmap trackers on broadcast footage. Practitioners often bolt TrackNetV2 onto YOLO to cover misses. — [arXiv:2306.10293](https://arxiv.org/pdf/2306.10293), [PMC service-fault study](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10747833/)
- **Published models:** Multiple community shuttlecock datasets/models on Roboflow Universe and YOLO11-based repos exist, but no authoritative benchmark-grade shuttlecock YOLO. — [Roboflow Universe](https://universe.roboflow.com/search?q=class:shuttlecock)
- **License — CONFIRMED and material:** Ultralytics YOLOv8/YOLO11 are **AGPL-3.0 by default**, and Ultralytics explicitly states this covers **both the training code and the model weights it produces**. Commercial/production use that embeds YOLO without open-sourcing your whole app requires a paid **Enterprise License**. This is a genuine commercial blocker unless you buy the enterprise license or use a non-Ultralytics detector. — [ultralytics.com/license](https://www.ultralytics.com/license), [Ultralytics enterprise discussion](https://github.com/orgs/ultralytics/discussions/1260)

## E. WASB re-implementations / successors with cleaner licensing

- **WASB itself is already the clean-license option:** **MIT (NTT Communications, 2023)**, PyTorch (tested Python 3.8 / CUDA 11.3), and its **Model Zoo ships badminton weights** for WASB, TrackNetV2, ResTrackNetV2, MonoTrack, DeepBall, BallSeg — all redistributed under NTT's MIT repo. WASB is the SOTA badminton result in its own harness: **WASB (Step=1) F1 93.1, Acc 89.0, AP 91.6; (Step=3) F1 91.6, Acc 87.0, AP 88.5** vs TrackNetV2 F1 90.5 / MonoTrack F1 90.9. Caveat: last repo push ~Nov 2023, so lightly maintained, but code is standard PyTorch. — [MODEL_ZOO.md](https://github.com/nttcom/WASB-SBDT/blob/main/MODEL_ZOO.md), [WASB Table 2](https://papers.bmvc2023.org/0310.pdf)
- **ResTrackNetV2** — WASB's own residual/transposed-conv TrackNetV2 variant, distributed under WASB's MIT repo with badminton weights (F1 89.4). A lighter (1.2M param) MIT-licensed alternative. — [MODEL_ZOO.md](https://github.com/nttcom/WASB-SBDT/blob/main/MODEL_ZOO.md)
- **Successors to watch (not yet vetted for license/weights):** TrackNetV4 (motion-attention fusion, plug-and-play on V2/V3), and a 2024 preprint **TrackNetV5** ([arXiv:2512.02789](https://arxiv.org/pdf/2512.02789)). Flagged as leads only — I did not confirm their licenses or that they beat WASB on the badminton benchmark.

---

## Load-bearing open questions (verify before any commercial ship)

1. **The badminton training/benchmark dataset has NO license.** The NYCU/TrackNetV2 "Shuttlecock Trajectory Dataset" (used by TrackNetV2, both TrackNetV3s, MonoTrack, **and WASB**) states **no license, copyright, or usage terms** on its distribution pages. It is broadcast-match footage; commercial reuse is legally unclear and likely **not** cleanly permitted without contacting NYCU. An MIT *code* license does **not** launder the dataset terms into the resulting weights. — [dataset HackMD](https://hackmd.io/Nf8Rh1NrSrqNUzmO0sQKZw), [GitLab repo](https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNetv2)
2. **MonoTrack is noncommercial-only** (Adobe Research License) — do not use its code/weights in a product.
3. **Ultralytics YOLO is AGPL-3.0** including produced weights — enterprise license required for closed-source commercial use.
4. **WASB/TrackNetV3 MIT covers the code, not the pretrained weights' data provenance.** The weights were trained on the unlicensed NYCU dataset, so the cleanest commercial path is: use WASB's **MIT code/architecture** but **retrain on data you have rights to**.
5. TrackNetV3 accuracy numbers (97.51% / 90.53%) come from each repo's own eval, **not** WASB's protocol — treat cross-paper F1 comparisons as non-comparable; only WASB's Table 2 puts TrackNetV2/MonoTrack/WASB on one ruler.

Primary sources to keep: WASB `LICENSE.md` and `MODEL_ZOO.md` (`github.com/nttcom/WASB-SBDT`), the [BMVC WASB PDF](https://papers.bmvc2023.org/0310.pdf) (Table 2), the [dataset HackMD](https://hackmd.io/Nf8Rh1NrSrqNUzmO0sQKZw), and the [MonoTrack Adobe Research LICENSE](https://github.com/jhwang7628/monotrack/blob/master/LICENSE).
