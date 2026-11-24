"""Deterministic UTF-8 byte tokenizer owned by Vayron.

Byte tokenization is multilingual-safe but inefficient compared with learned
subword tokenizers. Special-token spellings are stable for readable debugging.
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
        self._special_spellings = {
            self.config.bos_id: "<|bos|>",
            self.config.eos_id: "<|eos|>",
            self.config.pad_id: "<|pad|>",
        }

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
        pieces: list[str] = []
        raw = bytearray()

        def flush_bytes() -> None:
            if raw:
                pieces.append(raw.decode("utf-8", errors="replace"))
                raw.clear()

        for token in token_ids:
            if isinstance(token, bool) or not isinstance(token, int):
                raise TypeError("token ids must be integers")
            if 0 <= token <= 255:
                raw.append(token)
            elif token in self._special_spellings:
                if not skip_special_tokens:
                    flush_bytes()
                    pieces.append(self._special_spellings[token])
            else:
                raise ValueError(f"Token id out of range: {token}")
        flush_bytes()
        return "".join(pieces)

    def to_dict(self) -> dict[str, int | str]:
        return {"type": "utf8-byte", **self.config.__dict__}
