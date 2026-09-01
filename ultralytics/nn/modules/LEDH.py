import math
import torch
import torch.nn as nn

from ultralytics.nn.modules import Detect, Conv, DFL

class GroupConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=0, groups=None):
        super().__init__()
        if groups is None:
            groups = in_channels // 16

        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride=stride, padding=padding,
                              groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU(inplace=True)

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))
    

class LEDH(Detect):
    def __init__(self, nc: int = 80, reg_max=16, end2end=False, ch: tuple = ()):
        """
        初始化 LEDH 检测头
        Args:
            nc (int): 类别数，默认 80 (COCO)
            reg_max (int): DFL 回归的最大值，控制边框的离散化粒度，默认 16
            end2end (bool): 是否启用端到端（End2End）模式（如 RT-DETR 风格），默认 False
            ch (tuple): 每个检测头输入特征图的通道数列表，例如 (128, 256, 512, 1024)
                        对应 P2, P3, P4, P5
        """
        super().__init__(nc, reg_max, end2end, ch)
        self.shared_transform = nn.ModuleList()

        # 共享特征变换模块：双层 GroupConv
        for c in ch:
            self.shared_transform.append(
                nn.Sequential(
                    GroupConv(c, c, kernel_size=3, padding=1),
                    GroupConv(c, c, kernel_size=3, padding=1),
                )
            )

        # 回归分支
        self.cv2 = nn.ModuleList([
            nn.Conv2d(c, 4 * self.reg_max, kernel_size=1)
            for c in ch
        ])

        # 分类分支
        self.cv3 = nn.ModuleList([
            nn.Conv2d(c, self.nc, kernel_size=1)
            for c in ch
        ])

        # 端到端分支
        if end2end:
            self.one2one_cv2 = nn.ModuleList([
                nn.Conv2d(c, 4 * self.reg_max, kernel_size=1) for c in ch
            ])
            self.one2one_cv3 = nn.ModuleList([
                nn.Conv2d(c, self.nc, kernel_size=1) for c in ch
            ])
            self._end2end = True
        else:
            self.one2one_cv2 = self.one2one_cv3 = None
            self._end2end = False

    def forward_head(
        self, x: list[torch.Tensor], box_head: torch.nn.Module = None, cls_head: torch.nn.Module = None
    ) -> dict[str, torch.Tensor]:
        if box_head is None or cls_head is None:
            return dict()
        
        bs = x[0].shape[0]  # batch size
        boxes_list = []
        scores_list = []

         # 遍历每个特征层
        for i, feat in enumerate(x):
            # 共享特征变换
            shared_feat = self.shared_transform[i](feat) # F_i

            # 回归分支
            box_out = box_head[i](shared_feat) # (bs, 4*reg_max, H, W)
            # 展平为 (bs, 4*reg_max, H*W)
            boxes_list.append(box_out.view(bs, 4 * self.reg_max, -1))

            # 分类分支
            cls_out = cls_head[i](shared_feat) # (bs, nc, H, W)
            # 展平为 (bs, nc, H*W)
            scores_list.append(cls_out.view(bs, self.nc, -1))

        # 将所有特征层的预测在最后一维（anchor 数量）拼接
        boxes = torch.cat(boxes_list, dim=-1)
        scores = torch.cat(scores_list, dim=-1)

        return dict(boxes=boxes, scores=scores, feats=x)
    
    def bias_init(self):
        for i, (box_conv, cls_conv) in enumerate(zip(self.cv2, self.cv3)):
            # 回归偏置
            if hasattr(box_conv, 'bias') and box_conv.bias is not None:
                box_conv.bias.data[:] = 2.0

            # 分类偏置
            if hasattr(cls_conv, 'bias') and cls_conv.bias is not None:
                # 公式：log( 5 / nc / (640 / stride[i])^2 )
                # 使得正负样本的置信度初始区分度合理
                cls_conv.bias.data[:self.nc] = math.log(
                    5 / self.nc / (640 / self.stride[i]) ** 2
                )

        # 如果启用了 End2End，也对 one2one 分支做同样初始化
        if self.end2end and self.one2one_cv2 is not None:
            for i, (box_conv, cls_conv) in enumerate(zip(self.one2one_cv2, self.one2one_cv3)):
                if hasattr(box_conv, 'bias') and box_conv.bias is not None:
                    box_conv.bias.data[:] = 2.0
                if hasattr(cls_conv, 'bias') and cls_conv.bias is not None:
                    cls_conv.bias.data[:self.nc] = math.log(
                        5 / self.nc / (640 / self.stride[i]) ** 2
                    )