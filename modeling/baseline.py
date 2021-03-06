# encoding: utf-8
"""
@author:  liaoxingyu
@contact: sherlockliao01@gmail.com
"""

import copy

import torch
import random
from torch import nn

from .backbones.resnet import ResNet, BasicBlock, Bottleneck
from .backbones.resnet_ibn_a import resnet50_ibn_a
from .backbones.senet import SENet, SEResNetBottleneck, SEBottleneck, SEResNeXtBottleneck


class AttentionModule(nn.Module):
    def __init__(self, channels):
        super(AttentionModule, self).__init__()
        self.fc1 = nn.Conv2d(channels, 128, kernel_size=1, padding=0)
        self.relu = nn.ReLU(inplace=True)
        self.fc2 = nn.Conv2d(128, 8, kernel_size=1, padding=0)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.sigmoid(x)
        return x


def weights_init_kaiming(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        nn.init.kaiming_normal_(m.weight, a=0, mode='fan_out')
        nn.init.constant_(m.bias, 0.0)
    elif classname.find('Conv') != -1:
        nn.init.kaiming_normal_(m.weight, a=0, mode='fan_in')
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)
    elif classname.find('BatchNorm') != -1:
        if m.affine:
            nn.init.constant_(m.weight, 1.0)
            nn.init.constant_(m.bias, 0.0)


def weights_init_classifier(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        nn.init.normal_(m.weight, std=0.001)
        if m.bias:
            nn.init.constant_(m.bias, 0.0)


class BatchDrop(nn.Module):
    def __init__(self, h_ratio, w_ratio):
        super(BatchDrop, self).__init__()
        self.h_ratio = h_ratio
        self.w_ratio = w_ratio

    def forward(self, x):
        if self.training:
            h, w = x.size()[-2:]
            rh = round(self.h_ratio * h)
            rw = round(self.w_ratio * w)
            sx = random.randint(0, h - rh)
            sy = random.randint(0, w - rw)
            mask = x.new_ones(x.size())
            mask[:, :, sx:sx + rh, sy:sy + rw] = 0
            x = x * mask
        return x


class Baseline(nn.Module):
    in_planes = 2048

    def __init__(self, num_classes, last_stride, model_path, model_name,
                 pretrain_choice, attention=False):
        super(Baseline, self).__init__()
        self.attention = attention
        if model_name == 'resnet18':
            self.in_planes = 512
            self.base = ResNet(last_stride=last_stride,
                               block=BasicBlock,
                               layers=[2, 2, 2, 2])
        elif model_name == 'resnet34':
            self.in_planes = 512
            self.base = ResNet(last_stride=last_stride,
                               block=BasicBlock,
                               layers=[3, 4, 6, 3])
        elif model_name == 'resnet50':
            self.base = ResNet(last_stride=last_stride,
                               block=Bottleneck,
                               layers=[3, 4, 6, 3])
        elif model_name == 'resnet101':
            self.base = ResNet(last_stride=last_stride,
                               block=Bottleneck,
                               layers=[3, 4, 23, 3])
        elif model_name == 'resnet152':
            self.base = ResNet(last_stride=last_stride,
                               block=Bottleneck,
                               layers=[3, 8, 36, 3])

        elif model_name == 'se_resnet50':
            self.base = SENet(block=SEResNetBottleneck,
                              layers=[3, 4, 6, 3],
                              groups=1,
                              reduction=16,
                              dropout_p=None,
                              inplanes=64,
                              input_3x3=False,
                              downsample_kernel_size=1,
                              downsample_padding=0,
                              last_stride=last_stride)
        elif model_name == 'se_resnet101':
            self.base = SENet(block=SEResNetBottleneck,
                              layers=[3, 4, 23, 3],
                              groups=1,
                              reduction=16,
                              dropout_p=None,
                              inplanes=64,
                              input_3x3=False,
                              downsample_kernel_size=1,
                              downsample_padding=0,
                              last_stride=last_stride)
        elif model_name == 'se_resnet152':
            self.base = SENet(block=SEResNetBottleneck,
                              layers=[3, 8, 36, 3],
                              groups=1,
                              reduction=16,
                              dropout_p=None,
                              inplanes=64,
                              input_3x3=False,
                              downsample_kernel_size=1,
                              downsample_padding=0,
                              last_stride=last_stride)
        elif model_name == 'se_resnext50':
            self.base = SENet(block=SEResNeXtBottleneck,
                              layers=[3, 4, 6, 3],
                              groups=32,
                              reduction=16,
                              dropout_p=None,
                              inplanes=64,
                              input_3x3=False,
                              downsample_kernel_size=1,
                              downsample_padding=0,
                              last_stride=last_stride)
        elif model_name == 'se_resnext101':
            self.base = SENet(block=SEResNeXtBottleneck,
                              layers=[3, 4, 23, 3],
                              groups=32,
                              reduction=16,
                              dropout_p=None,
                              inplanes=64,
                              input_3x3=False,
                              downsample_kernel_size=1,
                              downsample_padding=0,
                              last_stride=last_stride)
        elif model_name == 'senet154':
            self.base = SENet(block=SEBottleneck,
                              layers=[3, 8, 36, 3],
                              groups=64,
                              reduction=16,
                              dropout_p=0.2,
                              last_stride=last_stride)
        elif model_name == 'resnet50_ibn_a':
            self.base = resnet50_ibn_a(last_stride)

        if pretrain_choice == 'imagenet':
            # if cfg.MODEL.ADD_TEST_MODE == 'no':
            self.base.load_param(model_path)
            print('Loading pretrained ImageNet model......')

        elif pretrain_choice == 'scratch':
            print('Training from scratch....')

        # output res_conv4_2
        self.backbone = nn.Sequential(
            self.base.layer0,
            self.base.layer1,
            self.base.layer2,
            self.base.layer3[0]
        )

        res_conv4 = nn.Sequential(*self.base.layer3[1:])

        res_g_conv5 = self.base.layer4

        res_p_conv5 = nn.Sequential(
            SEResNetBottleneck(1024, 512, groups=1, reduction=16,
                               downsample=nn.Sequential(nn.Conv2d(1024, 2048, 1, bias=False), nn.BatchNorm2d(2048))),
            SEResNetBottleneck(2048, 512, groups=1, reduction=16),
            SEResNetBottleneck(2048, 512, groups=1, reduction=16))
        res_p_conv5.load_state_dict(self.base.layer4.state_dict())

        self.p1 = nn.Sequential(copy.deepcopy(res_conv4), copy.deepcopy(res_g_conv5))
        self.p2 = nn.Sequential(copy.deepcopy(res_conv4), copy.deepcopy(res_p_conv5))
        self.p3 = nn.Sequential(copy.deepcopy(res_conv4), copy.deepcopy(res_p_conv5))

        # pool2d = nn.MaxPool2d
        # self.maxpool_zg_p1 = pool2d(kernel_size=(12, 4))
        # self.maxpool_zg_p2 = pool2d(kernel_size=(24, 8))
        # self.maxpool_zg_p3 = pool2d(kernel_size=(24, 8))
        # self.maxpool_zp2 = pool2d(kernel_size=(12, 8))
        # self.maxpool_zp3 = pool2d(kernel_size=(8, 8))

        self.maxpool_zg_p1 = nn.AdaptiveMaxPool2d(output_size=1)
        self.maxpool_zg_p2 = nn.AdaptiveMaxPool2d(output_size=1)
        self.maxpool_zg_p3 = nn.AdaptiveMaxPool2d(output_size=1)
        self.maxpool_zp2 = nn.AdaptiveMaxPool2d(output_size=(2, 1))
        self.maxpool_zp3 = nn.AdaptiveMaxPool2d(output_size=(3, 1))

        reduction = nn.Sequential(nn.Conv2d(2048, 256, 1, bias=False), nn.BatchNorm2d(256))

        self.relu = nn.ReLU()
        self._init_reduction(reduction)
        self.reduction_0 = copy.deepcopy(reduction)
        self.reduction_1 = copy.deepcopy(reduction)
        self.reduction_2 = copy.deepcopy(reduction)
        self.reduction_3 = copy.deepcopy(reduction)
        self.reduction_4 = copy.deepcopy(reduction)
        self.reduction_5 = copy.deepcopy(reduction)
        self.reduction_6 = copy.deepcopy(reduction)
        self.reduction_7 = copy.deepcopy(reduction)

        feat_size = 256

        self.fc_id_2048_0 = nn.Linear(feat_size, num_classes)
        self.fc_id_2048_1 = nn.Linear(feat_size, num_classes)
        self.fc_id_2048_2 = nn.Linear(feat_size, num_classes)

        self.fc_id_256_1_0 = nn.Linear(feat_size, num_classes)
        self.fc_id_256_1_1 = nn.Linear(feat_size, num_classes)
        self.fc_id_256_2_0 = nn.Linear(feat_size, num_classes)
        self.fc_id_256_2_1 = nn.Linear(feat_size, num_classes)
        self.fc_id_256_2_2 = nn.Linear(feat_size, num_classes)

        self._init_fc(self.fc_id_2048_0)
        self._init_fc(self.fc_id_2048_1)
        self._init_fc(self.fc_id_2048_2)

        self._init_fc(self.fc_id_256_1_0)
        self._init_fc(self.fc_id_256_1_1)
        self._init_fc(self.fc_id_256_2_0)
        self._init_fc(self.fc_id_256_2_1)
        self._init_fc(self.fc_id_256_2_2)

        if self.attention:
            self.feature_score = AttentionModule(6144)
            # conv
            nn.init.kaiming_normal_(self.feature_score.fc1.weight, mode='fan_in')
            nn.init.constant_(self.feature_score.fc1.bias, 0.)
            # conv
            nn.init.kaiming_normal_(self.feature_score.fc2.weight, mode='fan_in')
            nn.init.constant_(self.feature_score.fc2.bias, 0.)

        # if pretrain_choice == 'imagenet' and cfg.MODEL.ADD_TEST_MODE == 'yes':
        #     self.load_param(model_path)
        #     print('===========================================')

    @staticmethod
    def _init_fc(fc):
        nn.init.kaiming_normal_(fc.weight, mode='fan_out')
        nn.init.constant_(fc.bias, 0.)

    def _init_reduction(self, reduction):
        # conv
        nn.init.kaiming_normal_(reduction[0].weight, mode='fan_in')

        # bn
        nn.init.normal_(reduction[1].weight, mean=1., std=0.02)
        nn.init.constant_(reduction[1].bias, 0.)

    def forward(self, x):

        x = self.backbone(x)

        p1 = self.p1(x)
        p2 = self.p2(x)
        p3 = self.p3(x)

        zg_p1 = self.maxpool_zg_p1(p1)
        zg_p2 = self.maxpool_zg_p2(p2)
        zg_p3 = self.maxpool_zg_p3(p3)

        zp2 = self.maxpool_zp2(p2)
        z0_p2 = zp2[:, :, 0:1, :]
        z1_p2 = zp2[:, :, 1:2, :]

        zp3 = self.maxpool_zp3(p3)
        z0_p3 = zp3[:, :, 0:1, :]
        z1_p3 = zp3[:, :, 1:2, :]
        z2_p3 = zp3[:, :, 2:3, :]

        fg_p1 = self.reduction_0(zg_p1).squeeze(dim=3).squeeze(dim=2)
        fg_p2 = self.reduction_1(zg_p2).squeeze(dim=3).squeeze(dim=2)
        fg_p3 = self.reduction_2(zg_p3).squeeze(dim=3).squeeze(dim=2)
        f0_p2 = self.reduction_3(z0_p2).squeeze(dim=3).squeeze(dim=2)
        f1_p2 = self.reduction_4(z1_p2).squeeze(dim=3).squeeze(dim=2)
        f0_p3 = self.reduction_5(z0_p3).squeeze(dim=3).squeeze(dim=2)
        f1_p3 = self.reduction_6(z1_p3).squeeze(dim=3).squeeze(dim=2)
        f2_p3 = self.reduction_7(z2_p3).squeeze(dim=3).squeeze(dim=2)

        if self.attention:
            attention_p = torch.cat((zg_p1, zg_p2, zg_p3), dim=1)
            scores = self.feature_score(attention_p).squeeze(dim=3).squeeze(dim=2)

            fg_p1 = scores[:, 0].reshape((-1, 1)) * fg_p1
            fg_p2 = scores[:, 1].reshape((-1, 1)) * fg_p2
            fg_p3 = scores[:, 2].reshape((-1, 1)) * fg_p3
            f0_p2 = scores[:, 3].reshape((-1, 1)) * f0_p2
            f1_p2 = scores[:, 4].reshape((-1, 1)) * f1_p2
            f0_p3 = scores[:, 5].reshape((-1, 1)) * f0_p3
            f1_p3 = scores[:, 6].reshape((-1, 1)) * f1_p3
            f2_p3 = scores[:, 7].reshape((-1, 1)) * f2_p3

        l_p1 = self.fc_id_2048_0(self.relu(fg_p1))
        l_p2 = self.fc_id_2048_1(self.relu(fg_p2))
        l_p3 = self.fc_id_2048_2(self.relu(fg_p3))

        l0_p2 = self.fc_id_256_1_0(self.relu(f0_p2))
        l1_p2 = self.fc_id_256_1_1(self.relu(f1_p2))
        l0_p3 = self.fc_id_256_2_0(self.relu(f0_p3))
        l1_p3 = self.fc_id_256_2_1(self.relu(f1_p3))
        l2_p3 = self.fc_id_256_2_2(self.relu(f2_p3))

        #
        final_feature = torch.cat([fg_p1, fg_p2, fg_p3, f0_p2, f1_p2, f0_p3, f1_p3, f2_p3], dim=1)

        if self.training:
            return (l_p1, l_p2, l_p3, l0_p2, l1_p2, l0_p3, l1_p3, l2_p3), (fg_p1, fg_p2, fg_p3, final_feature)
        else:
            return final_feature

    def load_param(self, trained_path):

        param_dict = torch.load(trained_path)

        if not isinstance(param_dict, dict):
            param_dict = param_dict.state_dict()

        for i in param_dict:
            if 'classifier' in i:
                continue

            self.state_dict()[i].copy_(param_dict[i])
