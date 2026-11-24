import pytest

from vayron_core.tokenizer import VayronByteTokenizer


def test_round_trip_arabic_english_and_code():
    tokenizer = VayronByteTokenizer()
    text = "مرحبا Vayron — print('hello')"
    assert tokenizer.decode(tokenizer.encode(text)) == text


def test_special_tokens():
    tokenizer = VayronByteTokenizer()
    tokens = tokenizer.encode("AI", add_bos=True, add_eos=True)
    assert tokens[0] == tokenizer.config.bos_id
    assert tokens[-1] == tokenizer.config.eos_id
    assert tokenizer.decode(tokens) == "AI"


def test_special_tokens_are_visible_when_requested():
    tokenizer = VayronByteTokenizer()
    tokens = tokenizer.encode("AI", add_bos=True, add_eos=True)
    assert tokenizer.decode(tokens, skip_special_tokens=False) == "<|bos|>AI<|eos|>"


def test_invalid_token_rejected():
    with pytest.raises(ValueError):
        VayronByteTokenizer().decode([999])


def test_non_integer_token_rejected():
    with pytest.raises(TypeError):
        VayronByteTokenizer().decode([1.5])
