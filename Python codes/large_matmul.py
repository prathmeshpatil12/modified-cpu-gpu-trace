import torch, time, os
N = int(os.getenv("N", "4096"))
I = int(os.getenv("ITERS", "50"))
device = "cuda" if torch.cuda.is_available() else "cpu"
A = torch.randn(N, N, device=device)
B = torch.randn(N, N, device=device)
torch.cuda.synchronize() if device == "cuda" else None
for i in range(I):
    C = A @ B
    if device == "cuda":
        torch.cuda.synchronize()
    if (i+1) % 10 == 0:
        print(f"iter {i+1}/{I}")
print("Done large matmul")