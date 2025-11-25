#!/usr/bin/env python3
import os, time, torch

device = "cuda" if torch.cuda.is_available() else "cpu"

# Config via env
N          = int(os.getenv("MATMUL_N", "4096"))        # matrix size N x N
MAT_ITERS  = int(os.getenv("MATMUL_ITERS", "300"))      # big GEMM iterations
TINY_ITERS = int(os.getenv("TINY_ITERS", "100000"))     # tiny add iterations
REPORT_EVERY = int(os.getenv("REPORT_EVERY", "10"))

mode = os.getenv("MODE", "both")  # "large", "tiny", "both"

def section(title):
    print(f"\n=== {title} ===")

def time_sync():
    if device == "cuda":
        torch.cuda.synchronize()
    return time.time()

def large_matmul():
    section(f"Large Matmul N={N} iters={MAT_ITERS}")
    A = torch.randn(N, N, device=device)
    B = torch.randn(N, N, device=device)
    time_sync()
    start = time_sync()
    for i in range(MAT_ITERS):
        C = A @ B
        if device == "cuda":
            torch.cuda.synchronize()
        if (i+1) % REPORT_EVERY == 0:
            print(f"[GEMM] iter {i+1}/{MAT_ITERS}")
    end = time_sync()
    print(f"[GEMM] Elapsed: {end-start:.3f}s")

def tiny_kernels():
    section(f"Tiny Kernels iters={TINY_ITERS}")
    x = torch.zeros(1, device=device)
    time_sync()
    start = time_sync()
    for i in range(TINY_ITERS):
        x = x + 1  # launches many tiny kernels
        if (i+1) % (REPORT_EVERY*100) == 0:
            print(f"[TINY] iter {i+1}/{TINY_ITERS}")
    if device == "cuda":
        torch.cuda.synchronize()
    end = time_sync()
    print(f"[TINY] Final value: {x.item()}")
    print(f"[TINY] Elapsed: {end-start:.3f}s")

if mode in ("large", "both"):
    large_matmul()
if mode in ("tiny", "both"):
    tiny_kernels()
print("Done large_vs_tiny benchmark")