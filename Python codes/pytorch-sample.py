import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import models
import time

model = models.resnet18()
criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=0.001, momentum=0.9)

inputs = torch.randn(32, 3, 224, 224)
labels = torch.randint(0, 1000, (32,))

def run_model():
    for _ in range(10):
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

# Run the model
run_model()
print('Done')

# Getting C code pytorch is calling
