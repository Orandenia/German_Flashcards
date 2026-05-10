"""使用 pytest 的基础校验：词表文件与 load_vocabulary 行为。"""

from pathlib import Path

from app import load_vocabulary

_VOCAB_PATH = Path(__file__).resolve().parent / "vocabulary.json"


def test_vocabulary_json_loads_successfully() -> None:
    """项目根目录的 vocabulary.json 应能被 load_vocabulary 正常解析。"""
    words = load_vocabulary(_VOCAB_PATH)
    assert isinstance(words, list)
    assert all(isinstance(w, dict) for w in words)
    first = words[0]
    assert "de" in first and "zh" in first
    assert first["de"] and first["zh"]


def test_word_list_is_not_empty() -> None:
    """词表至少包含一条有效词条（与程序启动前校验一致）。"""
    words = load_vocabulary(_VOCAB_PATH)
    assert len(words) >= 1
