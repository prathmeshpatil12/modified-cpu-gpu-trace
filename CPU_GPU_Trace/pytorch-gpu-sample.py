import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import models
import time

# Check if CUDA is available
if torch.cuda.is_available():
    device = torch.device('cuda')
    print(f"Using GPU: {torch.cuda.get_device_name(0)}")
else:
    device = torch.device('cpu')
    print("CUDA not available, using CPU")

# Create model and move to GPU
model = models.resnet18().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=0.001, momentum=0.9)

# Create data on GPU
inputs = torch.randn(32, 3, 224, 224).to(device)
labels = torch.randint(0, 1000, (32,)).to(device)

def run_model():
    for i in range(100):  # More iterations to generate more GPU activity
        # print(f"Iteration {i+1}/100")
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        # Add some delay to make activities more visible
        time.sleep(0.1)

# Run the model
# print("Starting GPU computation...")
run_model()
print('GPU computation done!')
