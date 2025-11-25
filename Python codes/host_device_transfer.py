import torch, os, time
I = int(os.getenv("ITERS", "500"))
SZ = int(os.getenv("SIZE_MB", "64")) * 256 * 1024  # approx MB via elements (float32 ~4B)
cpu_tensor = torch.randn(SZ, device="cpu")
device = "cuda" if torch.cuda.is_available() else "cpu"
for i in range(I):
    t = cpu_tensor.to(device, non_blocking=True)
    back = t.to("cpu", non_blocking=True)
    if (i+1) % 50 == 0:
        print(f"iter {i+1}/{I}")
    if device == "cuda":
        torch.cuda.synchronize()
print("Transfers done")