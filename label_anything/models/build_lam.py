# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import torch
import torch.nn as nn

from label_anything.models.common import LayerNorm2d
from label_anything.models.common import SAM_EMBED_DIM
from label_anything.models.lam import MultiLevelLam
from label_anything.models.mask_decoder import AffinityDecoder, MultiLevelMaskDecoder
from label_anything.models.prompt_encoder import MultiLevelPromptEncoder
from label_anything.models.transformer import AffinityTransformer

from . import (
    ImageEncoderViT,
    MaskDecoderLam,
    PromptImageEncoder,
    Lam,
    BinaryLam,
    IdentityTransformer,
    OneWayTransformer,
    TwoWayTransformer,
    RandomMatrixEncoder,
)

from .build_encoder import (
    build_encoder,
    build_vit_b,
    build_vit_h,
    build_vit_l,
    build_vit_b_mae,
    build_vit_b_imagenet_i21k,
    build_vit_dino_b8,
)


def build_lam_vit_h(**kwargs):
    return _build_lam(
        build_vit_h,
        **kwargs,
    )


def build_lam_vit_l(**kwargs):
    return _build_lam(
        build_vit_l,
        **kwargs,
    )


def build_lam_vit_b(**kwargs):
    return _build_lam(
        build_vit_b,
        **kwargs,
    )


def build_lam_vit_mae_b(**kwargs):
    return _build_lam(
        build_vit_b_mae,
        **kwargs,
    )


def build_lam_vit_b_imagenet_i21k(**kwargs):
    return _build_lam(
        build_vit_b_imagenet_i21k,
        **kwargs,
    )

def build_lam_no_vit(**kwargs):
    return _build_lam(
        build_vit=None,
        use_vit=False,
        **kwargs,
    )

def build_lam_dino_b8(**kwargs):
    return _build_lam(
        build_vit_dino_b8,
        **kwargs,
    )
	
	
def build_optim_lam_no_vit(**kwargs):
    # Importazione locale per evitare l'importazione circolare
    from label_anything.models.lam import OptimizedLam
    print("AAAAA")
    # Estrai i parametri specifici di OptimizedLam
    optim_kwargs = {}
    if 'num_iterations' in kwargs:
        optim_kwargs['num_iterations'] = kwargs.pop('num_iterations')
    if 'learning_rate' in kwargs:
        optim_kwargs['learning_rate'] = kwargs.pop('learning_rate')
    
    # Ottieni un modello Lam normale senza ViT
    lam = _build_lam(
        build_vit=None,
        use_vit=False,
        **kwargs,
    )
    
    # Crea una nuova istanza di OptimizedLam
    optimized_lam = OptimizedLam(
        image_size=lam.image_size,
        image_encoder=lam.image_encoder,
        neck=lam.neck,
        prompt_encoder=lam.prompt_encoder,
        mask_decoder=lam.mask_decoder,
        custom_preprocess=lam.custom_preprocess
    )
    
    # Imposta i parametri specifici dopo la creazione
    if 'num_iterations' in optim_kwargs:
        optimized_lam.num_iterations = optim_kwargs['num_iterations']
    if 'learning_rate' in optim_kwargs:
        optimized_lam.learning_rate = optim_kwargs['learning_rate']
    
    # Copia i pesi
    optimized_lam.load_state_dict(lam.state_dict())
    
    return optimized_lam


def build_optim_lam_vit_b(**kwargs):
    # Importazione locale per evitare l'importazione circolare
    from label_anything.models.lam import OptimizedLam
    print("AAAAA")
    # Estrai i parametri specifici di OptimizedLam
    optim_kwargs = {}
    if 'num_iterations' in kwargs:
        optim_kwargs['num_iterations'] = kwargs.pop('num_iterations')
    if 'learning_rate' in kwargs:
        optim_kwargs['learning_rate'] = kwargs.pop('learning_rate')
    
    # Ottieni un modello Lam normale senza ViT
    lam = _build_lam(
        build_vit_b,
        **kwargs,
    )
    
    # Crea una nuova istanza di OptimizedLam
    optimized_lam = OptimizedLam(
        image_size=lam.image_size,
        image_encoder=lam.image_encoder,
        neck=lam.neck,
        prompt_encoder=lam.prompt_encoder,
        mask_decoder=lam.mask_decoder,
        custom_preprocess=lam.custom_preprocess
    )
    
    # Imposta i parametri specifici dopo la creazione
    if 'num_iterations' in optim_kwargs:
        optimized_lam.num_iterations = optim_kwargs['num_iterations']
    if 'learning_rate' in optim_kwargs:
        optimized_lam.learning_rate = optim_kwargs['learning_rate']
    
    # Copia i pesi
    optimized_lam.load_state_dict(lam.state_dict())
    
    return optimized_lam

def _build_lam(
    build_vit,
    checkpoint=None,
    use_sam_checkpoint=False,
    use_vit_sam_neck=True,
    use_vit=True,
    image_embed_dim=SAM_EMBED_DIM,
    embed_dim=SAM_EMBED_DIM,
    image_size=1024,
    vit_patch_size=16,
    class_attention=False,
    example_attention=False,
    example_class_attention=True,
    class_embedding_dim=None,
    spatial_convs=None,
    encoder_attention_downsample_rate: int = 2,
    decoder_attention_downsample_rate: int = 2,
    classification_layer_downsample_rate: int = 8,
    use_support_features_in_prompt_encoder: bool = True,
    fusion_transformer="TwoWayTransformer",  # "TwoWayTransformer" or "OneWayTransformer" or "IdentityTransformer"
    few_type="Prototype",  # "Prototype" or "Affinity" or "PrototypeAffinity"
    class_fusion="sum",
    transformer_keys_are_images=True,
    transformer_feature_size=None,
    class_encoder=None,
    segment_example_logits=False,
    dropout: float = 0.0,
    binary=False,
    custom_preprocess=True,
	  lam_class=None, 
):

    image_embedding_size = image_size // vit_patch_size

    vit = build_vit(project_last_hidden=use_vit_sam_neck) if use_vit else None
    if class_encoder is not None:
        cls = globals()[class_encoder["name"]]
        params = {k: v for k, v in class_encoder.items() if k != "name"}
        class_encoder = cls(**params)
    else:
        class_encoder = lambda x, y: (x, y)

    neck = (
        None
        if image_embed_dim == embed_dim
        else nn.Sequential(
            nn.Conv2d(
                image_embed_dim,
                embed_dim,
                kernel_size=1,
                bias=False,
            ),
            LayerNorm2d(embed_dim),
            nn.Conv2d(
                embed_dim,
                embed_dim,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            LayerNorm2d(embed_dim),
        )
    )
    if lam_class is None:
        lam_class = BinaryLam if binary else Lam

    lam = lam_class(
        image_size=image_size,
        image_encoder=vit,
        neck=neck,
        prompt_encoder=PromptImageEncoder(
            embed_dim=embed_dim,
            image_embedding_size=(image_embedding_size, image_embedding_size),
            input_image_size=(image_size, image_size),
            mask_in_chans=16,
            class_attention=class_attention,
            example_attention=example_attention,
            example_class_attention=example_class_attention,
            class_embedding_dim=class_embedding_dim,
            dropout=dropout,
            use_support_features=use_support_features_in_prompt_encoder,
            transformer=TwoWayTransformer(
                depth=2,
                embedding_dim=embed_dim,
                mlp_dim=2048,
                attention_downsample_rate=encoder_attention_downsample_rate,
                num_heads=8,
                dropout=dropout,
            ),
            class_encoder=class_encoder,
        ),
        mask_decoder=build_mask_decoder(
            embed_dim=embed_dim,
            spatial_convs=spatial_convs,
            segment_example_logits=segment_example_logits,
            fusion_transformer=fusion_transformer,
            decoder_attention_downsample_rate=decoder_attention_downsample_rate,
            classification_layer_downsample_rate=classification_layer_downsample_rate,
            transformer_feature_size=transformer_feature_size,
            dropout=dropout,
            few_type=few_type,
            class_fusion=class_fusion,
            transformer_keys_are_images=transformer_keys_are_images,
        ),
        custom_preprocess=custom_preprocess,
    )
    lam.eval()
    if checkpoint is not None:
        with open(checkpoint, "rb") as f:
            state_dict = torch.load(f)

        if use_sam_checkpoint:
            lam.init_pretrained_weights(state_dict)
        else:
            lam.load_state_dict(state_dict)
    return lam


def build_mask_decoder(
    embed_dim,
    decoder_attention_downsample_rate,
    few_type="Prototype",  # "Prototype" or "Affinity"
    fusion_transformer="TwoWayTransformer",  # "TwoWayTransformer" or "OneWayTransformer"
    segment_example_logits=False,
    spatial_convs=None,
    classification_layer_downsample_rate=8,
    conv_upsample_stride=2,
    transformer_feature_size=None,
    dropout=0.0,
    class_fusion="sum",
    prototype_merge=False,
    transformer_keys_are_images=True,
):
    if few_type == "Prototype":
        fusion_transformer = globals()[fusion_transformer](
            depth=2,
            embedding_dim=embed_dim,
            mlp_dim=2048,
            num_heads=8,
            attention_downsample_rate=decoder_attention_downsample_rate,
            dropout=dropout,
        )

        decoder = MaskDecoderLam(
            transformer_dim=embed_dim,
            spatial_convs=spatial_convs,
            transformer=fusion_transformer,
            segment_example_logits=segment_example_logits,
            classification_layer_downsample_rate=classification_layer_downsample_rate,
            conv_upsample_stride=conv_upsample_stride,
            dropout=dropout,
        )
    elif few_type == "Affinity" or few_type == "PrototypeAffinity":
        fusion_transformer = AffinityTransformer(
            depth=2,
            embedding_dim=embed_dim,
            mlp_dim=2048,
            num_heads=8,
            attention_downsample_rate=decoder_attention_downsample_rate,
            dropout=dropout,
        )
        decoder = AffinityDecoder(
            transformer_dim=embed_dim,
            spatial_convs=spatial_convs,
            transformer=fusion_transformer,
            classification_layer_downsample_rate=classification_layer_downsample_rate,
            transformer_feature_size=transformer_feature_size,
            class_fusion=class_fusion,
            prototype_merge=few_type == "PrototypeAffinity",
            transformer_keys_are_images=transformer_keys_are_images,
        )
    else:
        raise NotImplementedError(f"few_type {few_type} not implemented")
    return decoder


build_lam = _build_lam


def build_multilevel_lam(
    encoder,
    image_size=1024,
    class_attention=False,
    example_attention=False,
    example_class_attention=True,
    class_embedding_dim=None,
    spatial_convs=None,
    encoder_attention_downsample_rate: int = 2,
    decoder_attention_downsample_rate: int = 2,
    classification_layer_downsample_rate: int = 8,
    use_support_features_in_prompt_encoder: bool = True,
    fusion_transformer="TwoWayTransformer",  # "TwoWayTransformer" or "OneWayTransformer"
    few_type="Prototype",  # "Prototype" or "Affinity" or "PrototypeAffinity"
    class_fusion="sum",
    transformer_keys_are_images=True,
    transformer_feature_size=None,
    class_encoder=None,
    segment_example_logits=False,
    dropout: float = 0.0,
    binary=False,
):
    encoder = build_encoder(encoder)
    hidden_sizes = encoder.config.hidden_sizes

    class_encoders = []
    if class_encoder is not None:
        for i in range(len(hidden_sizes)):
            cls = globals()[class_encoder["name"]]
            params = {k: v for k, v in class_encoder.items() if k != "name"}
            params["embed_dim"] = hidden_sizes[i]
            class_encoders.append(cls(**params))
    else:
        class_encoders = [lambda x, y: (x, y) for _ in range(len(hidden_sizes))]

    prompt_encoders = nn.ModuleList(
        [
            PromptImageEncoder(
                embed_dim=hidden_size,
                image_embedding_size=(
                    image_size // (4 * (2**i)),
                    image_size // (4 * (2**i)),
                ),
                input_image_size=(image_size, image_size),
                mask_in_chans=16,
                class_attention=class_attention,
                example_attention=example_attention,
                example_class_attention=example_class_attention,
                class_embedding_dim=class_embedding_dim,
                dropout=dropout,
                use_support_features=use_support_features_in_prompt_encoder,
                transformer=TwoWayTransformer(
                    depth=2,
                    embedding_dim=hidden_size,
                    mlp_dim=2048,
                    attention_downsample_rate=encoder_attention_downsample_rate,
                    num_heads=8,
                    dropout=dropout,
                ),
                class_encoder=class_encoders[i],
            )
            for i, hidden_size in enumerate(hidden_sizes)
        ]
    )
    prompt_encoder = MultiLevelPromptEncoder(prompt_encoders)
    masd_decoders = nn.ModuleList(
        [
            build_mask_decoder(
                embed_dim=embed_dim,
                spatial_convs=spatial_convs,
                segment_example_logits=segment_example_logits,
                fusion_transformer=fusion_transformer,
                decoder_attention_downsample_rate=decoder_attention_downsample_rate,
                classification_layer_downsample_rate=1,
                conv_upsample_stride=1,
                transformer_feature_size=transformer_feature_size,
                dropout=dropout,
                few_type=few_type,
                class_fusion=class_fusion,
                transformer_keys_are_images=transformer_keys_are_images,
            )
            for embed_dim in hidden_sizes
        ]
    )
    mask_decoder = MultiLevelMaskDecoder(
        masd_decoders,
        embed_dims=hidden_sizes,
        segment_example_logits=segment_example_logits,
    )
    lam = MultiLevelLam(
        image_size=image_size,
        image_encoder=encoder,
        prompt_encoder=prompt_encoder,
        mask_decoder=mask_decoder,
        neck=None,
    )
    return lam
