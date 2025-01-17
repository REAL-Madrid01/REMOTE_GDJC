# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import torch

from .box_head.box_head import build_roi_box_head
from .mask_head.mask_head import build_roi_mask_head
from .maskiou_head.maskiou_head import build_roi_maskiou_head

class CombinedROIHeads(torch.nn.ModuleDict):
    """
    Combines a set of individual heads (for box prediction or masks) into a single
    head.
    """

    def __init__(self, cfg, heads):
        super(CombinedROIHeads, self).__init__(heads)
        self.cfg = cfg.clone()
        if cfg.MODEL.MASK_ON and cfg.MODEL.ROI_MASK_HEAD.SHARE_BOX_FEATURE_EXTRACTOR:
            self.mask.feature_extractor = self.box.feature_extractor

    def forward(self, features, proposals, targets=None):
        losses = {}
        # TODO rename x to roi_box_features, if it doesn't increase memory consumption
        x, detections, loss_box = self.box(features, proposals, targets)
        losses.update(loss_box)
        if self.cfg.MODEL.MASK_ON:
            mask_features = features
            # optimization: during training, if we share the feature extractor between
            # the box and the mask heads, then we can reuse the features already computed
            if (
                self.training
                and self.cfg.MODEL.ROI_MASK_HEAD.SHARE_BOX_FEATURE_EXTRACTOR
            ):
                mask_features = x
            # During training, self.box() will return the unaltered proposals as "detections"
            # this makes the API consistent during training and testing
            if not self.cfg.MODEL.MASKIOU_ON:
                x, detections, loss_mask = self.mask(mask_features, detections, targets)
                losses.update(loss_mask)
            else:
                x, detections, loss_mask, roi_feature, selected_mask, labels, maskiou_targets = self.mask(mask_features, detections, targets)
                losses.update(loss_mask)
                
                loss_maskiou, detections = self.maskiou(roi_feature, detections, selected_mask, labels, maskiou_targets)
                losses.update(loss_maskiou)
        return x, detections, losses


def build_roi_heads(cfg):
    # individually create the heads, that will be combined together
    # afterwards
    roi_heads = []
    if not cfg.MODEL.RPN_ONLY:
        print("--->>构造roi_box_head--<<<")
        roi_heads.append(("box", build_roi_box_head(cfg)))
    if cfg.MODEL.MASK_ON:
        print("--->>构造roi_mask_head--<<<")
        roi_heads.append(("mask", build_roi_mask_head(cfg)))
        if cfg.MODEL.MASKIOU_ON:
            print("--->>构造roi_maskiou_head--<<<")
            roi_heads.append(("maskiou", build_roi_maskiou_head(cfg)))
    # combine individual heads in a single module
    if roi_heads:
        roi_heads = CombinedROIHeads(cfg, roi_heads)

    return roi_heads
