from ultralytics.nn.modules.C2PSA_EMA import C2PSA_EMA
import torch

if __name__ == '__main__':
    batch_size, channels, height, width = 4, 64, 32, 32
    x = torch.randn(batch_size, channels, height, width)
    model = C2PSA_EMA(channels, channels)
    y = model(x)
    print(y.shape)