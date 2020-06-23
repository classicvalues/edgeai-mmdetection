_base_ = [
    '../_jacinto_ai_base_/hyper_params/common_config.py',
    '../_jacinto_ai_base_/hyper_params/retinanet_config.py',
    '../_jacinto_ai_base_/hyper_params/schedule_1x.py',
]

dataset_type = 'CocoDataset'

if dataset_type == 'VOCDataset':
    _base_ += ['../_jacinto_ai_base_/datasets/voc0712_det.py']
    num_classes = 20
elif dataset_type == 'CocoDataset':
    _base_ += ['../_jacinto_ai_base_/datasets/coco_det.py']
    num_classes = 80
elif dataset_type == 'CityscapesDataset':
    _base_ += ['../_jacinto_ai_base_/datasets/cityscapes_det.py']
    num_classes = 8
else:
    assert False, f'Unknown dataset_type: {dataset_type}'


input_size = (768,384)                           # (1536,768) #(1024,512) #(768,384) #(512,512)
decoder_width_fact = 1                           # 1, 2, 3

backbone_type = 'RegNet'
backbone_arch = 'regnetx_800mf'                  # 'regnetx_800mf' #'regnetx_1.6gf'
to_rgb = False                                   # pycls regnet backbones are trained with bgr

regnet_settings = {
    'regnetx_800mf':{'regnet_base_channels':32, 'bacbone_out_channels':[64, 128, 288, 672], 'group_size_dw':16,
                      'fpn_out_channels':min(64*decoder_width_fact,256), 'retinanet_stacked_convs':3, 'fpn_num_blocks':3,
                      'pretrained':'open-mmlab://regnetx_800mf'},
    'regnetx_1.6gf':{'regnet_base_channels':32, 'bacbone_out_channels':[72, 168, 408, 912], 'group_size_dw':24,
                     'fpn_out_channels':min(96*decoder_width_fact,256), 'retinanet_stacked_convs':4, 'fpn_num_blocks':4,
                     'pretrained':'open-mmlab://regnetx_1.6gf'}}

regnet_cfg = regnet_settings[backbone_arch]
pretrained=regnet_cfg['pretrained']
regnet_base_channels=regnet_cfg['regnet_base_channels']
bacbone_out_channels=regnet_cfg['bacbone_out_channels']
backbone_out_indices = (0, 1, 2, 3)

fpn_type = 'JaiFPN' #'JaiFPN' #'JaiBiFPN'
fpn_in_channels = bacbone_out_channels
fpn_out_channels = regnet_cfg['fpn_out_channels']
fpn_start_level = 1
fpn_num_outs = 5
fpn_upsample_cfg=dict(scale_factor=2, mode='nearest') if fpn_type == 'JaiBiFPN' \
    else dict(scale_factor=2, mode='bilinear')
fpn_cfg = dict(num_blocks=regnet_cfg['fpn_num_blocks']) if fpn_type == 'JaiBiFPN' \
    else dict()

#retinanet_base_stride = (8 if fpn_start_level==1 else (4 if fpn_start_level==0 else None))
retinanet_stacked_convs = regnet_cfg['retinanet_stacked_convs']
pipeline_size_divisor = 128 if fpn_type == 'JaiBiFPN' else 32

# for multi-scale training, add more resolutions, but it may need much longer training schedule.
# for example: [(input_size[0], (input_size[1]*8)//10),(input_size[0], (input_size[1]*9)//10), input_size]
input_size_ms = [input_size]

conv_cfg = dict(type='ConvDWSep', group_size_dw=regnet_cfg['group_size_dw'])
norm_cfg = dict(type='BN')
act_cfg = dict(type='ReLU') if fpn_type == 'JaiBiFPN' else None

img_norm_cfg = dict(mean=[128.0, 128.0, 128.0], std=[64.0, 64.0, 64.0], to_rgb=to_rgb)

model = dict(
    type='RetinaNet',
    pretrained=pretrained,
    backbone=dict(
        type=backbone_type,
        arch=backbone_arch,
        base_channels=regnet_base_channels,
        out_indices=backbone_out_indices,
        norm_eval=False,
        style='pytorch'),
    neck=dict(
        type=fpn_type,
        in_channels=fpn_in_channels,
        out_channels=fpn_out_channels,
        start_level=fpn_start_level,
        num_outs=fpn_num_outs,
        add_extra_convs='on_input', #'on_output',
        upsample_cfg=fpn_upsample_cfg,
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        act_cfg=act_cfg,
        **fpn_cfg),
    bbox_head=dict(
        type='JaiRetinaHead',
        num_classes=num_classes,
        in_channels=fpn_out_channels,
        stacked_convs=retinanet_stacked_convs,
        feat_channels=fpn_out_channels,
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        anchor_generator=dict(
            type='AnchorGenerator',
            octave_base_scale=4,
            scales_per_octave=3,
            ratios=[0.5, 1.0, 2.0],
            strides=[8, 16, 32, 64, 128]),
        bbox_coder=dict(
            type='DeltaXYWHBBoxCoder',
            target_means=[.0, .0, .0, .0],
            target_stds=[1.0, 1.0, 1.0, 1.0]),
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=2.0,
            alpha=0.25,
            loss_weight=1.0),
        loss_bbox=dict(type='L1Loss', loss_weight=1.0)))

# dataset settings
train_pipeline = [
    dict(type='LoadImageFromFile'),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(
        type='Resize',
        img_scale=input_size_ms,
        multiscale_mode='value',
        keep_ratio=True),
    dict(type='RandomFlip', flip_ratio=0.5),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='Pad', size_divisor=pipeline_size_divisor),
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
            dict(type='RandomFlip'),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='Pad', size_divisor=pipeline_size_divisor),
            dict(type='ImageToTensor', keys=['img']),
            dict(type='Collect', keys=['img']),
        ])
]

data = dict(
    samples_per_gpu=16,
    workers_per_gpu=3,
    train=dict(dataset=dict(pipeline=train_pipeline)),
    val=dict(pipeline=test_pipeline),
    test=dict(pipeline=test_pipeline))

# settings for qat or calibration - uncomment after doing floating point training
# also change dataset_repeats in the dataset config to 1 for fast learning
quantize = False #'training' #'calibration'
if quantize:
  load_from = './work_dirs/retinanet_regnet_fpn_bgr/latest.pth'
  optimizer = dict(type='SGD', lr=1e-3, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
  lr_config = dict(policy='CosineAnealing', min_lr_ratio=1e-3, warmup='linear', warmup_iters=100, warmup_ratio=1e-4)
  total_epochs = 1 if quantize == 'calibration' else 5
#else:
#  optimizer = dict(type='SGD', lr=1e-2, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
#


