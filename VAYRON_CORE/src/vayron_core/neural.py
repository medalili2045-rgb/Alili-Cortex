"""Small original decoder-only Transformer baseline (PyTorch optional extra)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

try:
    import torch
    from torch import nn
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise ImportError("Install Vayron training extras: pip install -e '.[train]'") from exc


@dataclass(frozen=True)
class VayronModelConfig:
    vocab_size: int = 259
    d_model: int = 128
    n_heads: int = 4
    n_layers: int = 4
    max_seq_len: int = 256
    dropout: float = 0.1
    mlp_ratio: int = 4

    def validate(self) -> None:
        if self.vocab_size < 259:
            raise ValueError("vocab_size must include byte and special tokens (>=259)")
        if self.d_model <= 0 or self.n_heads <= 0 or self.n_layers <= 0 or self.mlp_ratio <= 0:
            raise ValueError("model dimensions and mlp_ratio must be positive")
        if self.d_model % self.n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        if self.max_seq_len < 2:
            raise ValueError("max_seq_len must be >= 2")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")


class CausalSelfAttention(nn.Module):
    def __init__(self, config: VayronModelConfig) -> None:
        super().__init__()
        self.heads = config.n_heads
        self.head_dim = config.d_model // config.n_heads
        self.qkv = nn.Linear(config.d_model, 3 * config.d_model, bias=False)
        self.proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.dropout = nn.Dropout(config.dropout)
        mask = torch.tril(torch.ones(config.max_seq_len, config.max_seq_len, dtype=torch.bool))
        self.register_buffer("causal_mask", mask, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, length, width = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)

        def split(t: torch.Tensor) -> torch.Tensor:
            return t.view(batch, length, self.heads, self.head_dim).transpose(1, 2)

        q, k, v = split(q), split(k), split(v)
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        scores = scores.masked_fill(~self.causal_mask[:length, :length], torch.finfo(scores.dtype).min)
        weights = self.dropout(torch.softmax(scores, dim=-1))
        output = (weights @ v).transpose(1, 2).contiguous().view(batch, length, width)
        return self.dropout(self.proj(output))


class TransformerBlock(nn.Module):
    def __init__(self, config: VayronModelConfig) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(config.d_model)
        self.attention = CausalSelfAttention(config)
        self.norm2 = nn.LayerNorm(config.d_model)
        self.mlp = nn.Sequential(
            nn.Linear(config.d_model, config.mlp_ratio * config.d_model),
            nn.GELU(),
            nn.Linear(config.mlp_ratio * config.d_model, config.d_model),
            nn.Dropout(config.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attention(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class VayronLanguageModel(nn.Module):
    """A small decoder baseline with learned positional embeddings and tied weights."""

    def __init__(self, config: VayronModelConfig) -> None:
        super().__init__()
        config.validate()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position_embedding = nn.Embedding(config.max_seq_len, config.d_model)
        self.blocks = nn.ModuleList([TransformerBlock(config) for _ in range(config.n_layers)])
        self.final_norm = nn.LayerNorm(config.d_model)
        self.output = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.output.weight = self.token_embedding.weight
        self.apply(self._initialize)

    @staticmethod
    def _initialize(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        if not isinstance(input_ids, torch.Tensor) or input_ids.ndim != 2:
            raise ValueError("input_ids must be a tensor with shape [batch, sequence]")
        if input_ids.dtype != torch.long:
            raise TypeError("input_ids must use torch.long token IDs")
        if input_ids.shape[0] == 0 or input_ids.shape[1] == 0:
            raise ValueError("input_ids batch and sequence dimensions cannot be empty")
        if input_ids.shape[1] > self.config.max_seq_len:
            raise ValueError("sequence exceeds configured max_seq_len")
        if torch.any(input_ids < 0) or torch.any(input_ids >= self.config.vocab_size):
            raise ValueError("input token ID is outside the configured vocabulary")
        positions = torch.arange(input_ids.shape[1], device=input_ids.device)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)[None, :, :]
        for block in self.blocks:
            x = block(x)
        return self.output(self.final_norm(x))

    def forward_multimodal(
        self, input_ids: torch.Tensor, image_embeddings: torch.Tensor
    ) -> torch.Tensor:
        """Run image-prefix plus text tokens; return logits for text positions only."""
        if not isinstance(input_ids, torch.Tensor) or input_ids.ndim != 2:
            raise ValueError("input_ids must be a tensor with shape [batch, sequence]")
        if input_ids.dtype != torch.long:
            raise TypeError("input_ids must use torch.long token IDs")
        if input_ids.shape[0] == 0 or input_ids.shape[1] == 0:
            raise ValueError("input_ids batch and sequence dimensions cannot be empty")
        if torch.any(input_ids < 0) or torch.any(input_ids >= self.config.vocab_size):
            raise ValueError("input token ID is outside the configured vocabulary")
        if not isinstance(image_embeddings, torch.Tensor) or image_embeddings.ndim != 3:
            raise ValueError("image_embeddings must have shape [batch, patches, d_model]")
        if image_embeddings.shape[0] != input_ids.shape[0]:
            raise ValueError("image and text batch sizes must match")
        if image_embeddings.shape[1] < 1 or image_embeddings.shape[2] != self.config.d_model:
            raise ValueError("image_embeddings must contain patches with d_model width")
        if image_embeddings.device != input_ids.device:
            raise ValueError("image_embeddings and input_ids must be on the same device")
        total_length = image_embeddings.shape[1] + input_ids.shape[1]
        if total_length > self.config.max_seq_len:
            raise ValueError("combined image and text sequence exceeds max_seq_len")

        text = self.token_embedding(input_ids)
        x = torch.cat((image_embeddings, text), dim=1)
        positions = torch.arange(total_length, device=input_ids.device)
        x = x + self.position_embedding(positions)[None, :, :]
        for block in self.blocks:
            x = block(x)
        return self.output(self.final_norm(x[:, image_embeddings.shape[1]:]))

    def config_dict(self) -> dict:
        return asdict(self.config)

    @torch.no_grad()
    def generate(self, input_ids: torch.Tensor, *, max_new_tokens: int = 64) -> torch.Tensor:
        if not isinstance(input_ids, torch.Tensor) or input_ids.ndim != 2:
            raise ValueError("input_ids must be a tensor with shape [batch, sequence]")
        if input_ids.dtype != torch.long:
            raise TypeError("input_ids must use torch.long token IDs")
        if input_ids.shape[0] == 0 or input_ids.shape[1] == 0:
            raise ValueError("generation prompt cannot be empty")
        if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or not 0 <= max_new_tokens <= 8192:
            raise ValueError("max_new_tokens must be an integer between 0 and 8192")
        if torch.any(input_ids < 0) or torch.any(input_ids >= self.config.vocab_size):
            raise ValueError("input token ID is outside the configured vocabulary")
        self.eval()
        generated = input_ids
        for _ in range(max_new_tokens):
            context = generated[:, -self.config.max_seq_len:]
            logits = self(context)[:, -1, :]
            next_token = torch.argmax(logits, dim=-1, keepdim=True)
            generated = torch.cat((generated, next_token), dim=1)
        return generated
