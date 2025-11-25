### pytorch-gpu-sample.py
- What it does: Trains a ResNet18 for 100 iterations on a random batch (32×3×224×224), computing forward, loss, backward, SGD step; inserts time.sleep(0.1) each loop.
- Benchmark focus: General CNN training (mixed conv / BN / FC kernels) with artificial idle gaps; shows GPU vs CPU activity separation and kernel variety.

### large_matmul.py
- What it does: Repeated large dense matrix multiply (A @ B) of size N×N (default 4096) for I iterations, synchronizing each time.
- Benchmark focus: Pure compute-bound GEMM stressing high FLOP kernels; good for peak GPU utilization and energy per FLOP.

### tiny_kernels.py
- What it does: Runs 20k successive scalar add operations on a 1-element tensor.
- Benchmark focus: Kernel launch overhead and CPU dispatch cost; many very short GPU kernels.

### host_device_transfer.py
- What it does: Alternating host→device and device→host copies of a large random tensor for many iterations.
- Benchmark focus: PCIe (or NVLink) bandwidth and memcpy energy; highlights transfer vs compute.

### mixed_precision_training.py
- What it does: Mini CNN forward/backward with torch.cuda.amp GradScaler (Adam optimizer) for given iterations.
- Benchmark focus: Mixed precision (FP16/FP32) kernel mix vs full precision; conversion and scaling overhead.

### multi_streams.py
- What it does: Launches two concurrent matrix multiplies each iteration on separate CUDA streams.
- Benchmark focus: Kernel concurrency, stream scheduling, overlap potential; reveals simultaneous execution timing and energy sharing.

### transformer_inference.py
- What it does: Loads a pretrained causal LM (default gpt2) and repeatedly generates 32 new tokens from a fixed prompt.
- Benchmark focus: Inference workload with attention softmax, layernorm, small/medium kernels; stresses launch diversity and memory access.

### embedding_sparse.py
- What it does: Sparse embedding lookups (500k vocab, dim 128) with random indices and simple loss; SGD updates over many iterations.
- Benchmark focus: Memory-bound sparse access patterns, potential CPU involvement, irregular kernel shapes.

### tiny_op_chain.py
- What it does: Applies sin + add on a large 1M-element tensor repeatedly.
- Benchmark focus: Elementwise chain (memory bandwidth / latency bound) vs compute-bound; shows many moderate kernels.

### large_matmul vs tiny_kernels pairing
- Contrast: One large GEMM vs many trivial launches to compare energy and time attribution differences.

Summary:
Each script isolates a characteristic: compute-bound (GEMM), launch overhead (tiny_kernels), transfer bandwidth (host_device_transfer), precision effects (mixed_precision_training), concurrency (multi_streams), inference pattern (transformer_inference), sparse memory (embedding_sparse), elementwise memory-bound (tiny_op_chain), and mixed realistic CNN training with idle gaps (pytorch-gpu-sample).