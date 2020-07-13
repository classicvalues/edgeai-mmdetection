# optimizer
optimizer = dict(type='SGD', lr=1e-2, momentum=0.9, weight_decay=1e-4)

# gradient clipping - adopted from fcos config
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))

# warmup by iterations
# warmup_cfg = dict(warmup='linear', warmup_iters=500, warmup_ratio=1e-3)
# warmup by epoch
warmup_cfg = dict(warmup='linear', warmup_by_epoch=True, warmup_iters=1, warmup_ratio=1e-4)

# lr policy - step
# lr_config = dict(policy='step', step=[8, 11], **warmup_cfg)
# lr policy - cosine
lr_config = dict(policy='CosineAnealing', min_lr_ratio=1e-4, **warmup_cfg)

# runtime settings
total_epochs = 12


