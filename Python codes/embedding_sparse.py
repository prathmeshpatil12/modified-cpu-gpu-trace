import torch, os
I = int(os.getenv("ITERS", "3000"))
device = "cuda" if torch.cuda.is_available() else "cpu"
emb = torch.nn.Embedding(500000, 128).to(device)
opt = torch.optim.SGD(emb.parameters(), lr=0.01)
for i in range(I):
    idx = torch.randint(0, 500000, (1024,), device=device)
    vecs = emb(idx)
    loss = (vecs.mean() - 0.5)**2
    opt.zero_grad(set_to_none=True)
    loss.backward()
    opt.step()
    if (i+1) % 100 == 0:
        print(f"iter {i+1}/{I} loss={loss.item():.4f}")
print("Sparse embedding training done")