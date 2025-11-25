import torch, os
I = int(os.getenv("ITERS", "20000"))
device = "cuda" if torch.cuda.is_available() else "cpu"
x = torch.zeros(1, device=device)
for i in range(I):
    x = x + 1  # launch many tiny kernels
print("Final:", x.item())