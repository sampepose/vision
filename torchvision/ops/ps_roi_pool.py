import torch
from torch import nn

from torch.autograd import Function
from torch.autograd.function import once_differentiable

from torch.nn.modules.utils import _pair

from torchvision.extension import _lazy_import
from ._utils import convert_boxes_to_roi_format


class _PSRoIPoolFunction(Function):
    @staticmethod
    def forward(ctx, input, rois, output_size, spatial_scale):
        ctx.output_size = _pair(output_size)
        ctx.spatial_scale = spatial_scale
        ctx.input_shape = input.size()
        _C = _lazy_import()
        output, channel_mapping = _C.ps_roi_pool_forward(
            input, rois, spatial_scale, output_size[0], output_size[1]
        )
        ctx.save_for_backward(rois, channel_mapping)
        return output

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_output):
        rois, channel_mapping = ctx.saved_tensors
        output_size = ctx.output_size
        spatial_scale = ctx.spatial_scale
        bs, ch, h, w = ctx.input_shape
        _C = _lazy_import()
        grad_input = _C.ps_roi_pool_backward(
            grad_output,
            rois,
            channel_mapping,
            spatial_scale,
            output_size[0],
            output_size[1],
            bs, ch, h, w,
        )
        return grad_input, None, None, None


def ps_roi_pool(input, boxes, output_size, spatial_scale=1.0):
    """
    Performs Position-Sensitive Region of Interest (RoI) Pool operator
    described in R-FCN

    Arguments:
        input (Tensor[N, C, H, W]): input tensor
        boxes (Tensor[K, 5] or List[Tensor[L, 4]]): the box coordinates in (x1, y1, x2, y2)
            format where the regions will be taken from. If a single Tensor is passed,
            then the first column should contain the batch index. If a list of Tensors
            is passed, then each Tensor will correspond to the boxes for an element i
            in a batch
        output_size (int or Tuple[int, int]): the size of the output after the cropping
            is performed, as (height, width)
        spatial_scale (float): a scaling factor that maps the input coordinates to
            the box coordinates. Default: 1.0

    Returns:
        output (Tensor[K, C, output_size[0], output_size[1]])
    """
    rois = boxes
    if not isinstance(rois, torch.Tensor):
        rois = convert_boxes_to_roi_format(rois)
    return _PSRoIPoolFunction.apply(input, rois, output_size, spatial_scale)


class PSRoIPool(nn.Module):
    """
    See ps_roi_pool
    """
    def __init__(self, output_size, spatial_scale):
        super(PSRoIPool, self).__init__()
        self.output_size = output_size
        self.spatial_scale = spatial_scale

    def forward(self, input, rois):
        return ps_roi_pool(input, rois, self.output_size, self.spatial_scale)

    def __repr__(self):
        tmpstr = self.__class__.__name__ + "("
        tmpstr += "output_size=" + str(self.output_size)
        tmpstr += ", spatial_scale=" + str(self.spatial_scale)
        tmpstr += ")"
        return tmpstr
