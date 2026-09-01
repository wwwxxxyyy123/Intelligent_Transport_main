import torch
import torch.nn as nn
from .conv import Conv
from .block import C2PSA, PSABlock

class EMA(nn.Module):
    def __init__(self, channels, factor=32):
        super().__init__()
        """
        Args:
            channels: 输入特征图的通道数 (C)
            factor:   分组数，用于将通道划分为多个子组
        """

        self.groups = factor
        assert channels // self.groups > 0

        self.softmax = nn.Softmax(-1)

        self.agp = nn.AdaptiveAvgPool2d((1, 1))
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))

        self.gn = nn.GroupNorm(channels // self.groups, channels // self.groups)

        self.conv1x1 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=1, stride=1, padding=0)
        self.conv3x3 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        """
        Args:
            x: 输入特征图，形状为 (B, C, H, W)
        Returns:
            与 x 形状相同的增强特征图
        """
        b, c, h, w = x.size()

        # 通道分组：(B, C, H, W) -> (B*groups, C//groups, H, W)
        grouped_features = x.reshape(b * self.groups, -1, h, w)

        # 多尺度池化与注意力生成分支
        pooled_h = self.pool_h(grouped_features) # (B*groups, C//groups, H//groups, 1) 水平方向池化
        pooled_w = self.pool_w(grouped_features).permute(0, 1, 3, 2)  # (B*groups, C//groups, 1, W//groups) 垂直方向池化
        concat_hw = torch.cat([pooled_h, pooled_w], dim=2) # (B*groups, C//groups, H//groups, W//groups)
        hw_attn = self.conv1x1(concat_hw)

        attn_h, attn_w = torch.split(hw_attn, [h, w], dim=2) # (B*groups, C//groups, H//groups, 1) and (B*groups, C//groups, 1, W//groups)
        x1 = self.gn(grouped_features * attn_h.sigmoid() * attn_w.permute(0, 1, 3, 2).sigmoid())

        # 3x3卷积分支
        x2 = self.conv3x3(grouped_features)

        x11 = self.softmax(
            self.agp(x1).reshape(b * self.groups, -1, 1).permute(0, 2, 1)
        ) # (B*groups, 1, C//groups)
        x12 = x2.reshape(b * self.groups, c // self.groups, -1) # (B*groups, C//groups, H*W)

        x21 = self.softmax(
            self.agp(x2).reshape(b * self.groups, -1, 1).permute(0, 2, 1)
        )  # (B*groups, 1, C//groups)
        x22 = x1.reshape(b * self.groups, c // self.groups, -1) # (B*groups, C//groups, H*W)

        weights = (torch.matmul(x11, x12) + torch.matmul(x21, x22)).reshape(b * self.groups, 1, h, w)

        return (grouped_features * weights.sigmoid()).reshape(b, c, h, w)



class PSABlock_EMA(nn.Module):
    def __init__(self, c: int, factor: int = 32, shortcut: bool = True) -> None:
        """Initialize the PSABlock_EMA module.
        Args:
            c (int): Input and output channels.
            factor (int): Group factor for EMA.
            shortcut (bool): Whether to use shortcut connections.
        """
        super().__init__()
        self.ema = EMA(c, factor=factor)
        self.ffn = nn.Sequential(Conv(c, c * 2, 1), Conv(c * 2, c, 1, act=False))
        self.add = shortcut


    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Execute a forward pass through PSABlock_EMA module.

        Args:
            x (torch.Tensor): Input tensor.

        Returns:
            (torch.Tensor): Output tensor after attention and feed-forward processing.
        """
        x = x + self.ema(x) if self.add else self.ema(x)
        x = x + self.ffn(x) if self.add else self.ffn(x)
        return x
    

class C2PSA_EMA(nn.Module):
    def __init__(self, c1: int, c2: int, n: int = 1, e: float = 0.5):
        """Initialize C2PSA_EMA module.

        Args:
            c1 (int): Input channels.
            c2 (int): Output channels.
            n (int): Number of PSABlock_EMA modules.
            e (float): Expansion ratio.
        """
        super().__init__()
        assert c1 == c2
        self.c = int(c1 * e)
        self.cv1 = Conv(c1, 2 * self.c, 1, 1)
        self.cv2 = Conv(2 * self.c, c1, 1)

        self.m = nn.Sequential(*(PSABlock_EMA(self.c, factor=32) for _ in range(n)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Process the input tensor through a series of PSABlock_EMA modules.
        Args:
            x (torch.Tensor): Input tensor.
        Returns:
            (torch.Tensor): Output tensor after processing.
        """
        a, b = self.cv1(x).split((self.c, self.c), dim=1)
        b = self.m(b)
        return self.cv2(torch.cat((a, b), 1))

