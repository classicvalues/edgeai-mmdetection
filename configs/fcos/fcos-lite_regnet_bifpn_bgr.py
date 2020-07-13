_base_ = [
    '../_xbase_/hyper_params/common_config.py',
    '../_xbase_/hyper_params/retinanet_config.py',
    '../_xbase_/hyper_params/schedule_60e.py',
]

dataset_type = 'CocoDataset'

if dataset_type == 'CocoDataset':
    _base_ += ['../_xbase_/datasets/coco_det_1x.py']
    num_classes = 80
elif dataset_type == 'VOCDataset':
    _base_ += ['../_xbase_/datasets/voc0712_det_1x.py']
    num_classes = 20
elif dataset_type == 'CityscapesDataset':
    _base_ += ['../_xbase_/datasets/cityscapes_det_1x.py']
    num_classes = 8
else:
    assert False, f'Unknown dataset_type: {dataset_type}'


input_size = (768,384)                          # (1536,768) #(1024,512) #(768,384) #(512,512)
decoder_fpn_type = 'BiFPNLite'                  # 'FPNLite' #'BiFPNLite' #'FPN'
decoder_conv_type = 'ConvDWSep'                 # 'ConvDWSep' #'ConvDWTripletRes' #'ConvDWTripletAlwaysRes'
decoder_width_fact = (2 if decoder_fpn_type == 'BiFPNLite' else 4)
decoder_depth_fact = 4

img_norm_cfg = dict(mean=[103.53, 116.28, 123.675], std=[57.375, 57.12, 58.395], to_rgb=False) #imagenet mean used in pycls (bgr)

backbone_type = 'RegNet'
backbone_arch = 'regnetx_800mf'                  # 'regnetx_800mf' #'regnetx_1.6gf'
to_rgb = False                                   # pycls regnet backbones are trained with bgr

regnet_settings = {
    'regnetx_800mf':{'bacbone_out_channels':[64, 128, 288, 672], 'group_size_dw':16,
                      'fpn_out_channels':min(64*decoder_width_fact,256), 'head_stacked_convs':decoder_depth_fact,
                      'fpn_num_blocks':decoder_depth_fact, 'pretrained':'open-mmlab://regnetx_800mf'},
    'regnetx_1.6gf':{'bacbone_out_channels':[72, 168, 408, 912], 'group_size_dw':24,
                     'fpn_out_channels':min(96*decoder_width_fact,256), 'head_stacked_convs':decoder_depth_fact,
                     'fpn_num_blocks':decoder_depth_fact, 'pretrained':'open-mmlab://regnetx_1.6gf'}}

regnet_cfg = regnet_settings[backbone_arch]
pretrained=regnet_cfg['pretrained']
bacbone_out_channels=regnet_cfg['bacbone_out_channels']
backbone_out_indices = (0, 1, 2, 3)

fpn_in_channels = bacbone_out_channels
fpn_out_channels = regnet_cfg['fpn_out_channels']
fpn_start_level = 1
fpn_num_outs = 5
fpn_upsample_mode = 'bilinear' #'nearest' #'bilinear'
fpn_upsample_cfg = dict(scale_factor=2, mode=fpn_upsample_mode)
fpn_num_blocks = regnet_cfg['fpn_num_blocks']
fpn_bifpn_cfg = dict(num_blocks=fpn_num_blocks) if decoder_fpn_type == 'BiFPNLite' else dict()

input_size_divisor = 128 if decoder_fpn_type == 'BiFPNLite' else 32

#for multi-scale training, add more resolutions, but it may need much longer training schedule.
#input_size_ms = [input_size]
# setup the limits
input_size_frac = (0.34, 0.34) if input_size_divisor > 64 else (0.2, 0.2)
# construct a list of scales
input_size_ms = [(input_size[0]+sz_max_idx*input_size_divisor, input_size[1]) for sz_max_idx in range(-4,2)] + \
                [(input_size[0], input_size[1]+sz_min_idx*input_size_divisor) for sz_min_idx in range(-4,2)]
# select the suitable range
input_size_ms = [isz for isz in input_size_ms if isz[0] >= isz[1] and
                 isz[0] >= input_size[0]*(1-input_size_frac[0]) and isz[0] <= input_size[0]*(1+input_size_frac[0]) and
                 isz[1] >= input_size[1]*(1-input_size_frac[1]) and isz[1] <= input_size[1]*(1+input_size_frac[1])]

fcos_num_levels = 5
fcos_base_stride = (8 if fpn_start_level==1 else (4 if fpn_start_level==0 else None))
fcos_stacked_convs = regnet_cfg['fcos_stacked_convs']

conv_cfg = dict(type=decoder_conv_type, group_size_dw=regnet_cfg['group_size_dw']) #None
norm_cfg = dict(type='BN')

#head_base_stride = (8 if fpn_start_level==1 else (4 if fpn_start_level==0 else None))
head_stacked_convs = regnet_cfg['head_stacked_convs']

if fcos_num_levels > 1:
    fcos_input_size_max_edge = max(input_size)//2
    fcos_regress_range_start = fcos_input_size_max_edge//(2**(fcos_num_levels-1))
    fcos_pow2_factors = [2**i for i in range(fcos_num_levels)]
    fcos_regress_range_edges = [-1] + [fcos_regress_range_start*p2 for p2 in fcos_pow2_factors[1:]] + [1e8]
    fcos_regress_ranges = tuple([(fcos_regress_range_edges[i],fcos_regress_range_edges[i+1]) for i in range(fcos_num_levels)])
    fpn_num_outs = max(fcos_num_levels, len(backbone_out_indices))
    fcos_head_strides = [fcos_base_stride*p2 for p2 in fcos_pow2_factors]
else:
    fcos_regress_ranges = ((-1,1e8),)
    fpn_num_outs = len(backbone_out_indices)
    fcos_head_strides = [fcos_base_stride]
#

model = dict(
    type='FCOS',
    pretrained=pretrained,
    backbone=dict(
        type=backbone_type,
        arch=backbone_arch,
        out_indices=backbone_out_indices,
        norm_eval=False,
        style='pytorch'),
    neck=dict(
        type=decoder_fpn_type,
        in_channels=fpn_in_channels,
        out_channels=fpn_out_channels,
        start_level=fpn_start_level,
        num_outs=fpn_num_outs,
        add_extra_convs='on_input',
        upsample_cfg=fpn_upsample_cfg,
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        **fpn_bifpn_cfg),
    bbox_head=dict(
        type='FCOSLiteHead',
        num_classes=num_classes,
        in_channels=fpn_out_channels,
        stacked_convs=head_stacked_convs,
        feat_channels=fpn_out_channels,
        strides=fcos_head_strides,
        regress_ranges=fcos_regress_ranges,
        center_sample_radius=1.5,
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=1.5, #2.0 ->1.5
            alpha=0.25,
            loss_weight=1.0),
        loss_bbox=dict(type='IoULoss', loss_weight=4.0), #higher loss_weight
        loss_centerness=dict(type='CrossEntropyLoss', use_sigmoid=True, loss_weight=1.0)))

# dataset settings
train_pipeline = [
    dict(type='LoadImageFromFile', to_float32=True),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(
        type='PhotoMetricDistortion',
        brightness_delta=32,
        contrast_range=(0.5, 1.5),
        saturation_range=(0.5, 1.5),
        hue_delta=18),
    dict(
        type='Expand',
        mean=img_norm_cfg['mean'],
        to_rgb=img_norm_cfg['to_rgb'],
        ratio_range=(1, 4)),
    dict(
        type='MinIoURandomCrop',
        min_ious=(0.1, 0.3, 0.5, 0.7, 0.9),
        min_crop_size=0.3),
    dict(type='Resize', img_scale=input_size_ms, multiscale_mode='value', keep_ratio=True), #dict(type='Resize', img_scale=input_size, keep_ratio=True),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='RandomFlip', flip_ratio=0.5),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels']),
]

test_pipeline = [
    dict(type='LoadImageFromFile'),
    dict(
        type='MultiScaleFlipAug',
        img_scale=input_size,
        flip=False,
        transforms=[
            dict(type='Resize', keep_ratio=True),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='ImageToTensor', keys=['img']),
            dict(type='Collect', keys=['img']),
        ])
]

data = dict(
    samples_per_gpu=8,
    workers_per_gpu=0,
    train=dict(dataset=dict(pipeline=train_pipeline)),
    val=dict(pipeline=test_pipeline),
    test=dict(pipeline=test_pipeline))

# settings for qat or calibration - uncomment after doing floating point training
# also change dataset_repeats in the dataset config to 1 for fast learning
quantize = False #'training' #'calibration'
if quantize:
  load_from = './data/checkpoints/object_detection/fcos-lite_regnet_fpn_bgr/latest.pth'
  optimizer = dict(type='SGD', lr=1e-3, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
  total_epochs = 1 if quantize == 'calibration' else 5
else:
  optimizer = dict(type='SGD', lr=4e-2, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
  optimizer_config = dict(grad_clip=dict(max_norm=10.0, norm_type=2))
#
