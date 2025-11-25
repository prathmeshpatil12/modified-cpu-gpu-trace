import torch, os
device = "cuda" if torch.cuda.is_available() else "cpu"
if device != "cuda":
    print("CUDA not available"); exit()
I = int(os.getenv("ITERS", "500"))
stream1 = torch.cuda.Stream()
stream2 = torch.cuda.Stream()
A = torch.randn(2048,2048, device=device)
B = torch.randn(2048,2048, device=device)
for i in range(I):
    with torch.cuda.stream(stream1):
        C = A @ B
    with torch.cuda.stream(stream2):
        D = B @ A
    if (i+1) % 50 == 0:
        torch.cuda.synchronize()
        print(f"iter {i+1}/{I}")
torch.cuda.synchronize()
print("Multi-stream matmul done")