import torch, torch.nn as nn, torch.optim as optim, time, os
B = int(os.getenv("BATCH", "64"))
I = int(os.getenv("ITERS", "500"))
device = "cuda" if torch.cuda.is_available() else "cpu"
model = nn.Sequential(
    nn.Conv2d(3,64,3,padding=1),
    nn.ReLU(),
    nn.Conv2d(64,128,3,padding=1),
    nn.ReLU(),
    nn.AdaptiveAvgPool2d(1),
    nn.Flatten(),
    nn.Linear(128,10)
).to(device)
opt = optim.Adam(model.parameters(), lr=1e-3)
scaler = torch.cuda.amp.GradScaler(enabled=(device=="cuda"))
inputs = torch.randn(B,3,224,224, device=device)
labels = torch.randint(0,10,(B,), device=device)
for i in range(I):
    opt.zero_grad(set_to_none=True)
    with torch.cuda.amp.autocast(enabled=(device=="cuda")):
        out = model(inputs)
        loss = nn.functional.cross_entropy(out, labels)
    scaler.scale(loss).backward()
    scaler.step(opt)
    scaler.update()
    if (i+1) % 20 == 0:
        print(f"iter {i+1}/{I} loss={loss.item():.4f}")
print("Mixed precision training done")