# backend/inference/model.py

import torch
import torch.nn as nn
from transformers import AutoModel


class MultiHeadDeBERTa(nn.Module):
    """
    Inference-only version of the multi-head classifier.
    Identical architecture to training, but no loss computation.
    """
    
    def __init__(
        self,
        backbone_name: str,
        num_technique: int,
        num_emotion: int,
        num_subj: int,
        num_bias: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        self.backbone = AutoModel.from_pretrained(backbone_name)
        hidden_size = self.backbone.config.hidden_size
        self.shared_dropout = nn.Dropout(dropout)
        
        # Heads - MUST match training architecture exactly
        self.technique_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_technique),
        )
        
        self.emotion_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_emotion),
        )
        
        self.subjectivity_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 4, num_subj),
        )
        
        self.bias_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_bias),
        )
    
    def forward(self, input_ids, attention_mask, token_type_ids=None):
        """Inference-only forward pass — returns logits for all 4 heads."""
        kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            kwargs["token_type_ids"] = token_type_ids
        
        outputs = self.backbone(**kwargs)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.shared_dropout(cls_output)  # no-op at eval() time
        
        return {
            "technique_logits": self.technique_head(cls_output),
            "emotion_logits": self.emotion_head(cls_output),
            "subjectivity_logits": self.subjectivity_head(cls_output),
            "bias_logits": self.bias_head(cls_output),
        }