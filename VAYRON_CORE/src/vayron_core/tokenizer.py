"""Deterministic UTF-8 byte tokenizer owned by Vayron.

Byte tokenization is deliberately simple and multilingual-safe. It is a
baseline tokenizer, not a claim of optimal compression or language quality.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenizerConfig:
    vocab_size: int = 259
    bos_id: int = 256
    eos_id: int = 257
    pad_id: int = 258


class VayronByteTokenizer:
    def __init__(self) -> None:
        self.config = TokenizerConfig()

    @property
    def vocab_size(self) -> int:
        return self.config.vocab_size

    def encode(self, text: str, *, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        tokens = list(text.encode("utf-8"))
        if add_bos:
            tokens.insert(0, self.config.bos_id)
        if add_eos:
            tokens.append(self.config.eos_id)
        return tokens

    def decode(self, token_ids: list[int], *, skip_special_tokens: bool = True) -> str:
        raw = bytearray()
        for token in token_ids:
            if 0 <= token <= 255:
                raw.append(token)
            elif not skip_special_tokens and token in (self.config.bos_id, self.config.eos_id, self.config.pad_id):
                continue
            elif token not in (self.config.bos_id, self.config.eos_id, self.config.pad_id):
                raise ValueError(f"Token id out of range: {token}")
        return raw.decode("utf-8", errors="replace")

    def to_dict(self) -> dict[str, int | str]:
        return {"type": "utf8-byte", **self.config.__dict__}
