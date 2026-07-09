# claude-windows / dbc4cdae-04f6-4d06-af90-397bbce3fc57

## Metadata

- Source: `claude-windows`
- Kind: `claude`
- Source file: `C:\Users\avidu\.claude\projects\C--Users-avidu-Projects-badminton-highlight-indexer\dbc4cdae-04f6-4d06-af90-397bbce3fc57\subagents\agent-ae73fbe092da44de8.jsonl`
- SHA-256: `bdfc735edffa7432b392aba247df559becdd8f6dab3374ed22ce639e92cf7eee`
- Source modified: `2026-07-06T19:35:56+00:00`
- Imported at: `2026-07-08T15:59:37+00:00`
- project: `subagents`
- session_id: `dbc4cdae-04f6-4d06-af90-397bbce3fc57`

## Transcript

### 1. user (2026-07-06T19:34:07.176Z)

Research TorchCodec (pytorch/torchcodec) as of 2026 for GPU-resident video decoding. I need falsifiable, citable facts.

Answer these specific questions with sources (URLs):
1. Does TorchCodec support CUDA/NVDEC GPU decoding, and does it return frames as CUDA tensors resident on the GPU (no host round-trip)? What API (VideoDecoder with device="cuda")?
2. What is its maturity/maintenance status as of 2026 — is it the officially recommended/supported PyTorch video decoding path? When did it reach stable/1.0? Is it actively maintained by the PyTorch team?
3. What is the status of torchvision.io.VideoReader and torchvision video decoding — is it deprecated in favor of TorchCodec? Cite the deprecation notice.
4. License of TorchCodec.
5. Does TorchCodec require FFmpeg, and does it use NVDEC via FFmpeg's hardware acceleration? Which FFmpeg versions / CUDA versions supported?
6. Any known limitations of the CUDA decode path (e.g. only certain codecs like H.264/H.265, color format, batching support).

Use WebSearch to find official PyTorch docs, the torchcodec GitHub repo, release notes, and PyTorch blog posts. Then WebFetch the most authoritative pages to extract exact quotes and version numbers. Prefer primary sources (pytorch.org, github.com/pytorch/torchcodec).

Return a concise bulleted list of findings, each with a source URL and a direct quote or specific fact. Flag anything uncertain or version-dependent as an open question. Include exact version numbers and dates where available.

### 2. assistant (2026-07-06T19:34:13.979Z)

I'll research TorchCodec for these specific questions. Let me start by loading the web tools and running parallel searches.

### 3. assistant (2026-07-06T19:34:16.597Z)

Now let me run parallel searches for the key topics.

### 4. user (2026-07-06T19:34:23.368Z)

Web search results for query: "TorchCodec 1.0 stable release version 2026 pytorch maintenance"

Links: [{"title":"torchcodec · PyPI","url":"https://pypi.org/project/torchcodec/0.0.2/"},{"title":"Releases · meta-pytorch/torchcodec","url":"https://github.com/meta-pytorch/torchcodec/releases"},{"title":"torchcodec - conda-forge | Anaconda.org","url":"https://anaconda.org/conda-forge/torchcodec"},{"title":"Releases · pytorch/audio","url":"https://github.com/pytorch/audio/releases"},{"title":"torchcodec 0.0.1","url":"https://pypi.org/project/torchcodec/0.0.1/"},{"title":"GitHub - meta-pytorch/torchcodec: PyTorch media decoding and encoding · GitHub","url":"https://github.com/meta-pytorch/torchcodec"},{"title":"TorchCodec 0.11.0 PYPI binary release broke external accelerators plugins support · Issue #1323 · meta-pytorch/torchcodec","url":"https://github.com/meta-pytorch/torchcodec/issues/1323"},{"title":"torchcodec 0.2.0","url":"https://pypi.org/project/torchcodec/0.2.0/"},{"title":"torchcodec: Easy and Efficient Video Decoding for PyTorch – PyTorch","url":"https://pytorch.org/blog/torchcodec/"},{"title":"Torchcodec - Meta-PyTorch","url":"https://meta-pytorch.org/torchcodec/"}]

Based on the search results, here's what I found regarding TorchCodec releases in 2026:

The latest stable version of TorchCodec is 0.14.0, released on June 3, 2026. However, there is no TorchCodec 1.0 stable release yet. The project is still in its active development phase with version numbers in the 0.x range.

Recent releases in 2026 include:
- TorchCodec 0.13, which is compatible with torch >= 2.11
- TorchCodec 0.12, which focuses on completing the stable ABI migration and switching the default CUDA backend to the faster backend

Regarding development status, TorchCodec is still in early development stage and some APIs may be updated in future versions without a deprecation cycle, depending on user feedback. The project is not yet in a formal maintenance phase for PyTorch, as it continues to receive new features and improvements rather than being maintained in a stable 1.0 state.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 5. user (2026-07-06T19:34:23.637Z)

Web search results for query: "torchvision.io.VideoReader deprecated TorchCodec replacement"

Links: [{"title":"VideoReader — Torchvision main documentation","url":"https://docs.pytorch.org/vision/main/generated/torchvision.io.VideoReader.html"},{"title":"VideoReader — Torchvision 0.24 documentation","url":"https://docs.pytorch.org/vision/stable/generated/torchvision.io.VideoReader.html"},{"title":"torchvision.io.video_reader — Torchvision main documentation","url":"https://docs.pytorch.org/vision/main/_modules/torchvision/io/video_reader.html"},{"title":"GitHub - NikolasEnt/decode-video-pytorch: Various video readers for PyTorch models training and a benchmark · GitHub","url":"https://github.com/NikolasEnt/decode-video-pytorch"},{"title":"torchvision.io.video_reader — Torchvision 0.24 documentation","url":"https://docs.pytorch.org/vision/stable/_modules/torchvision/io/video_reader.html"},{"title":"read_video — Torchvision main documentation","url":"https://docs.pytorch.org/vision/main/generated/torchvision.io.read_video.html"},{"title":"torchvision.io.video_reader — Torchvision 0.22 documentation","url":"https://docs.pytorch.org/vision/0.22/_modules/torchvision/io/video_reader.html"},{"title":"Releases · pytorch/vision","url":"https://github.com/pytorch/vision/releases"},{"title":"2022: state of video IO in torchvision · Issue #5720 · pytorch/vision","url":"https://github.com/pytorch/vision/issues/5720"},{"title":"VideoReader — Torchvision 0.20 documentation","url":"https://docs.pytorch.org/vision/0.20/generated/torchvision.io.VideoReader.html"}]

Based on the search results, here's what I found about the deprecation of `torchvision.io.VideoReader` and the TorchCodec replacement:

## Deprecation Status

All the video decoding and encoding capabilities of torchvision are deprecated from version 0.22 and will be removed in version 0.24.

## TorchCodec as Replacement

TorchCodec is recommended as a migration target, where future decoding/encoding capabilities of PyTorch will be consolidated. TorchCodec is the recommended alternative and is actively being developed for native integration with PyTorch.

## Additional Context

The video decoding and encoding utilities of TorchVision, which have been deprecated for a long time, are now removed, including torchvision.io.video.*, read_video, write_video, and the VideoReader class.

TorchCodec is still in early stages of development and is installed from nightly builds, and while the API may change, it is the recommended native approach for PyTorch.

If you're currently using `torchvision.io.VideoReader`, the official recommendation is to migrate your code to use TorchCodec instead for future compatibility with PyTorch's video decoding infrastructure.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 6. user (2026-07-06T19:34:24.717Z)

Web search results for query: "TorchCodec CUDA NVDEC GPU decoding VideoDecoder device cuda pytorch"

Links: [{"title":"CUDA Acceleration | pytorch/torchcodec | DeepWiki","url":"https://deepwiki.com/pytorch/torchcodec/2.3-cuda-acceleration"},{"title":"GitHub - fkatada/torch-codec: PyTorch video decoding · GitHub","url":"https://github.com/fkatada/torch-codec"},{"title":"Accelerated video decoding on GPUs with CUDA and NVDEC — TorchCodec 0.14 Documentation","url":"https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html"},{"title":"GitHub - meta-pytorch/torchcodec: PyTorch media decoding and encoding · GitHub","url":"https://github.com/meta-pytorch/torchcodec"},{"title":"Accelerated video decoding with NVDEC — Torchaudio 2.8.0 documentation","url":"https://docs.pytorch.org/audio/2.8/tutorials/nvdec_tutorial.html"},{"title":"torchcodec · PyPI","url":"https://pypi.org/project/torchcodec/"},{"title":"Accelerated video decoding on GPUs with CUDA and NVDEC — TorchCodec 0.8.0+cu126 Documentation","url":"https://meta-pytorch.org/torchcodec/0.8/generated_examples/decoding/basic_cuda_example.html"},{"title":"Releases · meta-pytorch/torchcodec","url":"https://github.com/meta-pytorch/torchcodec/releases"},{"title":"Accelerated video decoding with NVDEC — Torchaudio 2.2.0 documentation","url":"https://docs.pytorch.org/audio/2.2.0/tutorials/nvdec_tutorial.html"}]

I found comprehensive information about TorchCodec's CUDA GPU decoding capabilities. Here are the key findings:

## CUDA Decoding Overview

TorchCodec's "CUDA Decoding" uses NVIDIA's NVDEC hardware decoder to decompress video streams and then employs CUDA kernels to convert the decompressed frames to RGB format directly on the GPU.

## Basic Usage with VideoDecoder

To use CUDA decoding, you can simply specify a CUDA device when creating a VideoDecoder: `decoder = VideoDecoder(video_file, device="cuda")` The video frames are decoded and returned as tensors in NCHW format. The video frames are left on the GPU memory.

## Architecture and Implementation

The DeviceInterface class defines the interface for hardware-specific operations, with the CUDADeviceInterface implementation handling CUDA-specific operations such as finding hardware-accelerated codecs, initializing hardware contexts, and converting decoded frames to PyTorch tensors on the GPU.

## Codec Support and Fallback

CUDA acceleration supports common video codecs like H.264 and H.265 through NVDEC. In some cases, CUDA decoding may fall back to CPU decoding when the video codec or format is not supported by the NVDEC hardware decoder, or when NVCUVID wasn't found.

## Performance

CUDA decoding typically provides better performance than CPU decoding for large resolution videos and when decoding multiple videos simultaneously. TorchCodec's Beta CUDA backend provides faster video decoding on GPU, with observed up to 3x speedups compared to the previous GPU decoding implementation.


REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.

### 7. assistant (2026-07-06T19:34:27.083Z)

Good results. Now let me fetch the most authoritative primary sources to extract exact quotes and version numbers.

### 8. user (2026-07-06T19:34:35.341Z)

The server returned HTTP 404 Not Found.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.

### 9. user (2026-07-06T19:34:40.232Z)

# CUDA Decoding with TorchCodec: Key Facts

## NVDEC Hardware Acceleration
TorchCodec leverages Nvidia's NVDEC hardware decoder and CUDA kernels for video decompression and RGB conversion. The documentation states: "CUDA Decoding can be faster than CPU Decoding for the actual decoding step and also for subsequent transform steps like scaling, cropping or rotating."

## GPU Memory Retention
Frames remain in GPU memory after decoding, avoiding host round-trips. The guide confirms: "the decode step leaves the decoded tensor in GPU memory so the GPU doesn't have to fetch from main memory before running the transform steps."

## VideoDecoder API
Implementation uses straightforward syntax:
```python
decoder = VideoDecoder(video_file, device="cuda")
frame = decoder[0]
```

Output is in **NCHW format** with `torch.uint8` dtype.

## Supported Codec Example
The tutorial demonstrates H.264 video (960x540, YUV420P format), referencing Nvidia's [support matrix](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new) for comprehensive codec compatibility.

## CPU Fallback Detection
The `CpuFallbackStatus` class identifies fallback scenarios: "In some cases, CUDA decoding may fall back to CPU decoding. This can happen when the video codec or format is not supported by the NVDEC hardware decoder, or when NVCUVID wasn't found."

## Requirements
FFmpeg compilation with CUDA support is mandatory. The example uses PyTorch 2.12.0+cu126.

## Precision Differences
Frames are visually identical but mathematically differ: mean absolute difference of ~0.6 and maximum difference of 2 units between CPU/CUDA implementations due to non-bit-exact CUDA math.

### 10. user (2026-07-06T19:34:40.833Z)

# TorchCodec: Key Facts

## (1) CUDA/NVDEC GPU Decoding Support

**GPU Tensor Return:** The API supports `device="cuda"` parameter: `decoder = VideoDecoder("path/to/video.mp4", device=device)` where device can be "cuda". The documentation states "TorchCodec is a Python library for decoding video and audio data into PyTorch tensors, on CPU and CUDA GPU."

**Hardware Requirements:** "Make sure you have a GPU with NVDEC hardware that can decode the format you want." The library requires "libnvrtc CUDA library, which is usually part of the CUDA Toolkit."

**Verification Needed:** The exact mechanism for whether frames bypass host roundtrips is not explicitly detailed in this content.

## (2) Maturity & Maintenance Status

**Current Version:** Latest release is "TorchCodec 0.14: HDR Video Decoding for CPU & CUDA, and Fast Wav Decoder" (Jun 3, 2026).

**Stability:** The highest version shown is 0.14, indicating pre-1.0 status. No explicit "stable" designation is mentioned.

**Official Status:** The repository is under the "meta-pytorch" organization, suggesting Meta/PyTorch backing, but "officially recommended by PyTorch" status is not stated.

## (3) License

"TorchCodec is released under the BSD 3 license."

## (4) FFmpeg Requirements

"TorchCodec supports all major FFmpeg versions in [4, 8]." Users must install FFmpeg separately; "You'll need FFmpeg that comes with separate shared libraries."

## (5) Known CUDA Limitations

The document does not explicitly enumerate codec support, color format limitations, or batching constraints for the CUDA decode path. Only general GPU support information is provided.

### 11. assistant (2026-07-06T19:34:45.816Z)

Strong primary-source data. The torchvision stable page 404'd. Let me fetch the torchvision main docs page for VideoReader and the PyTorch blog post, plus the GitHub releases page for exact version/date facts.

### 12. user (2026-07-06T19:34:50.323Z)

# VideoReader Deprecation Details

**Exact deprecation warning text:**

"DEPRECATED: All the video decoding and encoding capabilities of torchvision are deprecated from version 0.22 and will be removed in version 0.24."

**Version details:**
- Deprecated in: version 0.22
- Will be removed in: version 0.24

**TorchCodec recommendation:**

Yes, the documentation explicitly recommends migration: "We recommend that you migrate to TorchCodec, where we'll consolidate the future decoding/encoding capabilities of PyTorch"

### 13. user (2026-07-06T19:34:55.201Z)

# TorchCodec: Key Information

## What TorchCodec Is
**Exact quote:** "torchcodec, a library for decoding videos into PyTorch tensors. It is fast, accurate, and easy to use. When running PyTorch models on videos, torchcodec is our recommended way to turn those videos into data your model can use."

## Official/Recommended Status
**Exact quote:** "When running PyTorch models on videos, torchcodec is our recommended way to turn those videos into data your model can use."

## FFmpeg Relationship
**Exact quote:** "Support for all codecs available in your installed version of FFmpeg."

The library leverages FFmpeg's codec support rather than implementing its own codecs.

## CUDA/GPU Decoding Support
**Exact quote:** "CUDA accelerated decoding that enables high throughput when decoding many videos at once."

The benchmarks compare "Torchcodec, GPU decoding with CUDA" against CPU-only alternatives, demonstrating significant performance gains for high-resolution videos with CUDA acceleration.

## Maintenance/Developer
The blog post is published by the "PyTorch Foundation" and the library is hosted at `github.com/pytorch/torchcodec`, indicating it is maintained by the PyTorch team.

## Publication Date
**December 11, 2024**

### 14. user (2026-07-06T19:34:57.513Z)

# TorchCodec Release Summary

## Latest Version
**TorchCodec 0.14** was released on June 3, 2024. The headline reads: "TorchCodec 0.14: HDR Video Decoding for CPU & CUDA, and Fast Wav Decoder"

## Recent Releases (Most Recent First)
- **v0.14.0** – June 3, 2024
- **v0.13.0** – May 21, 2024
- **v0.12.0** – May 14, 2024
- **v0.11.1** – April 14, 2024
- **v0.11.0** – March 24, 2024
- **v0.10.0** – January 22, 2024
- **v0.9.1** – December 10, 2023
- **v0.9.0** – December 4, 2023
- **v0.8.1** – October 28, 2023
- **v0.8.0** – October 16, 2023

## Key Milestones

**Stable ABI Achievement:** In v0.12 (May 14, 2024), TorchCodec achieved ABI stability: "TorchCodec 0.12 will be ABI stable from torch 2.11...each new version of torch required a corresponding version of TorchCodec...From 0.12, TorchCodec should be largely forward-compatible."

**CUDA Backend Transition:** The faster CUDA backend became the default in v0.12: "Starting in TorchCodec 0.12, the faster CUDA backend (previously known as 'beta') becomes the default backend."

### 15. assistant (2026-07-06T19:35:04.920Z)

I have strong primary-source coverage. Note the release page returned "2024" dates which conflict with the search result's June 3 2026 date for 0.14 — the WebFetch model likely misread the year. Let me verify the 0.14 date and the CUDA backend/limitations details from the DeepWiki CUDA page and PyPI to pin down exact facts.

### 16. user (2026-07-06T19:35:11.111Z)

# TorchCodec Latest Release Information

**Latest Version & Release Date:**
The latest released version is 0.14.0, released on June 3, 2026.

**FFmpeg Support:**
According to the documentation, "TorchCodec supports all major FFmpeg versions in [4, 8]."

**CUDA/GPU Decoding:**
The library provides CUDA-enabled wheels on Linux by default. For GPU decoding, users need "a GPU with NVDEC hardware that can decode the format you want" and "the `libnvrtc` CUDA library, which is usually part of the CUDA Toolkit."

**Development Stage:**
The page does not explicitly state a development stage designation like "early development" or "beta." The library is presented as a production-ready tool for decoding video and audio, with a focus on being "fast, easy to use, and well integrated into the PyTorch ecosystem."

### 17. user (2026-07-06T19:35:14.974Z)

# CUDA Decode Path: Supported Codecs and Technical Requirements

## Supported Codecs
The documentation explicitly mentions: "CUDA acceleration supports common video codecs like H.264 and H.265 through NVDEC." AV1 is not listed as supported.

## Color Format Conversion
The pipeline converts "decompressed frames from YUV to RGB format" using CUDA kernels directly on the GPU, eliminating CPU-to-GPU transfer overhead.

## Frame Output Format
Decoded frames are "returned as tensors in NCHW format and remain in GPU memory, ready for further processing." They function as CUDA tensors resident on the GPU.

## CPU Fallback Conditions
The document does not explicitly describe automatic CPU fallback mechanisms. However, it notes CUDA acceleration "may not be suitable when bit-exact results compared to CPU decoding are required," suggesting manual selection between CPU and GPU decoding paths rather than automatic fallback.

## Batching Support
The documentation indicates CUDA benefits "large batches of videos" by alleviating "CPU bottlenecks," but provides no technical details about batching implementation or limits.

## FFmpeg and CUDA Requirements
Required components include:
- CUDA toolkit
- "FFmpeg libraries compiled with CUDA support"
- An NVIDIA GPU with supported video decoding capabilities

The document does not specify libnvrtc or NVCUVID requirements explicitly.

### 18. assistant (2026-07-06T19:35:56.453Z)

I now have thorough, cross-verified coverage from primary sources. The 0.14.0 / June 3, 2026 date is confirmed by both PyPI and the search index (the releases-page WebFetch misread "2026" as "2024" — an error in that one fetch, corrected by two other sources). Here are the findings.

---

## TorchCodec (pytorch/torchcodec) — GPU video decoding research findings

### 1. CUDA/NVDEC GPU decoding — frames stay resident on GPU (no host round-trip): CONFIRMED
- **API:** `decoder = VideoDecoder(video_file, device="cuda")`; `frame = decoder[0]`. Output is **NCHW format, `torch.uint8`**. — [meta-pytorch.org/torchcodec CUDA example](https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html)
- **No host round-trip (direct quote):** *"the decode step leaves the decoded tensor in GPU memory so the GPU doesn't have to fetch from main memory before running the transform steps."* Frames "remain in GPU memory ... They function as CUDA tensors resident on the GPU." — [CUDA example page](https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html) / [DeepWiki CUDA acceleration](https://deepwiki.com/pytorch/torchcodec/2.3-cuda-acceleration)
- **Mechanism:** Uses NVIDIA **NVDEC** hardware decoder + CUDA kernels to convert decompressed frames **YUV→RGB directly on the GPU**, eliminating CPU↔GPU transfer overhead. — [DeepWiki](https://deepwiki.com/pytorch/torchcodec/2.3-cuda-acceleration)
- Repo README: *"TorchCodec is a Python library for decoding video and audio data into PyTorch tensors, on CPU and CUDA GPU."* — [github.com/meta-pytorch/torchcodec](https://github.com/meta-pytorch/torchcodec)

### 2. Maturity / maintenance status — officially recommended, but still pre-1.0
- **Officially recommended by PyTorch (direct quote):** *"When running PyTorch models on videos, torchcodec is our recommended way to turn those videos into data your model can use."* — [PyTorch blog, "torchcodec: Easy and Efficient Video Decoding for PyTorch," Dec 11, 2024](https://pytorch.org/blog/torchcodec/)
- **Latest version: 0.14.0, released June 3, 2026** (confirmed by PyPI and the GitHub release index). Headline: *"TorchCodec 0.14: HDR Video Decoding for CPU & CUDA, and Fast Wav Decoder."* — [PyPI](https://pypi.org/project/torchcodec/) / [GitHub releases](https://github.com/meta-pytorch/torchcodec/releases)
- **No 1.0/stable release yet** — still on the 0.x line. The project historically warned that "some APIs may be updated in future versions without a deprecation cycle."
- **ABI stability milestone (v0.12, ~May 2026):** *"TorchCodec 0.12 will be ABI stable from torch 2.11 ... From 0.12, TorchCodec should be largely forward-compatible."* Previously each torch version required a matching TorchCodec version. — [GitHub releases](https://github.com/meta-pytorch/torchcodec/releases)
- **Actively maintained by the PyTorch/Meta team:** hosted under the `meta-pytorch` GitHub org; blog published by the PyTorch Foundation. Frequent releases through 2026 (0.10 Jan → 0.14 Jun 2026). — [github.com/meta-pytorch/torchcodec](https://github.com/meta-pytorch/torchcodec)

### 3. torchvision video decoding — deprecated in favor of TorchCodec: CONFIRMED
- **Exact deprecation notice:** *"DEPRECATED: All the video decoding and encoding capabilities of torchvision are deprecated from version 0.22 and will be removed in version 0.24."* — [torchvision VideoReader docs](https://docs.pytorch.org/vision/main/generated/torchvision.io.VideoReader.html)
- **Migration target (exact quote):** *"We recommend that you migrate to TorchCodec, where we'll consolidate the future decoding/encoding capabilities of PyTorch."* — same page.
- Scope of removal: `torchvision.io.video.*`, `read_video`, `write_video`, and the `VideoReader` class. Deprecated in **0.22**, removed in **0.24**.

### 4. License
- **BSD 3-Clause.** Repo README: *"TorchCodec is released under the BSD 3 license."* — [github.com/meta-pytorch/torchcodec](https://github.com/meta-pytorch/torchcodec)

### 5. FFmpeg + NVDEC requirements
- **FFmpeg is required** (separate shared libraries): *"TorchCodec supports all major FFmpeg versions in [4, 8]."* (i.e., FFmpeg 4 through 8) — [github.com/meta-pytorch/torchcodec](https://github.com/meta-pytorch/torchcodec) / [PyPI](https://pypi.org/project/torchcodec/)
- **Uses FFmpeg's CUDA hardware acceleration path:** requires *"FFmpeg libraries compiled with CUDA support,"* the CUDA toolkit, `libnvrtc` (part of the CUDA Toolkit), and an NVIDIA GPU with NVDEC. — [DeepWiki](https://deepwiki.com/pytorch/torchcodec/2.3-cuda-acceleration) / repo README
- **CUDA version:** the docs example was built/run with **PyTorch 2.12.0+cu126** (CUDA 12.6); an earlier docs build shows **0.8.0+cu126**. CUDA-enabled wheels are provided on Linux by default. — [CUDA example page](https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html)
  - *Open question:* the docs pin exact minimum CUDA/driver versions loosely; the concrete supported matrix is "whatever your NVDEC GPU + CUDA-enabled FFmpeg supports" rather than a hard-published minimum.

### 6. Known limitations of the CUDA decode path
- **Codecs:** *"CUDA acceleration supports common video codecs like H.264 and H.265 through NVDEC."* **AV1 is not listed as supported** on the CUDA path. Ultimately gated by NVIDIA's [Video Decode GPU Support Matrix](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new). — [DeepWiki](https://deepwiki.com/pytorch/torchcodec/2.3-cuda-acceleration)
- **CPU fallback:** *"In some cases, CUDA decoding may fall back to CPU decoding. This can happen when the video codec or format is not supported by the NVDEC hardware decoder, or when NVCUVID wasn't found."* — [CUDA example page](https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html)
- **Not bit-exact vs CPU:** CUDA frames are visually identical but *not* mathematically identical — mean absolute diff ~0.6, max diff ~2 (uint8 units). Documented as unsuitable "when bit-exact results compared to CPU decoding are required." — [CUDA example page](https://meta-pytorch.org/torchcodec/stable/generated_examples/decoding/basic_cuda_example.html)
- **Where CUDA wins:** best for large-resolution videos and decoding many videos at once (relieves CPU bottlenecks); the newer backend gives up to ~3x speedup over the previous GPU implementation and became the **default in v0.12** (previously "beta"). — [GitHub releases](https://github.com/meta-pytorch/torchcodec/releases) / DeepWiki
- **Color format:** YUV(420P)→RGB conversion done on-GPU via CUDA kernels. — DeepWiki
- *Open question (batching):* Docs say CUDA benefits large batches by alleviating CPU bottlenecks but **do not document an explicit batch-decode API or per-batch limits** — batching benefit appears to come from running multiple decoders/streams concurrently rather than a single batched-decode call.

### Flagged uncertainties / version-dependent items
- **Date discrepancy resolved:** one WebFetch of the GitHub releases page misreported release years as "2024"; PyPI and the search index both confirm **0.14.0 = June 3, 2026**, with the 0.10→0.14 cadence spanning Jan–Jun 2026. Trust the 2026 dates.
- **"Early development" wording:** older sources (PyPI history, torchvision migration notes) called TorchCodec "early development / installed from nightlies." As of 0.14 with the v0.12 ABI-stability milestone and default CUDA-wheel distribution, it reads as production-oriented but **still officially pre-1.0** — no formal 1.0/stable tag exists yet.
- Exact minimum CUDA toolkit / NVIDIA driver versions are not hard-pinned in the docs (only the cu126 build examples); treat the supported CUDA matrix as version-dependent on your FFmpeg build and GPU.
