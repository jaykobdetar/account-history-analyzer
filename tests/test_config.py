from pathlib import Path
import pytest
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.io import digest


def test_CFG_01_defaults_and_immutability():
    c = AnalysisConfig.from_toml()
    assert c['windows']['target_words'] == 1000
    with pytest.raises(TypeError):
        c['windows']['target_words'] = 5
    assert digest(c.analytical()) == digest(AnalysisConfig.from_toml('config/default.toml').analytical())


@pytest.mark.parametrize('data', [
    {'wat': 2}, {'style': {'wat': 2}}, {'input': {'strict': False}},
    {'input': {'max_unique_records': True}}, {'changes': {'primary_lambda': float('nan')}},
    {'windows': {'target_words': 0}}, {'style': {'ngram_lengths': [5, 3]}},
    {'reuse': {'near_threshold_denominator': 0}}, {'reuse': {'near_threshold_numerator': 101}},
    {'ai_text_detection': {'enabled': True}}, {'report': {'remote_assets': True}},
    {'style': {'views': ['raw_source']}}, {'style': {'ngram_lengths': []}},
])
def test_CFG_02_reject_invalid(data):
    with pytest.raises(InputError):
        AnalysisConfig.from_mapping(data)


def test_IN_16_reference_identity(tmp_path):
    data = Path('design_examples/delta_reference_toy.json').read_bytes()
    for name in ('a.json', 'b.json'):
        (tmp_path / name).write_bytes(data)
    def c(name):
        return AnalysisConfig.from_mapping({'delta': {'reference_path': str(tmp_path / name)}}, allow_toy_reference=True)
    assert c('a.json').analytical() == c('b.json').analytical()
    with pytest.raises(InputError, match='Toy'):
        AnalysisConfig.from_mapping({'delta': {'reference_path': str(tmp_path / 'a.json')}})


def test_reference_is_frozen_once(tmp_path):
    p=tmp_path/'ref.json'
    original=Path('design_examples/delta_reference_toy.json').read_bytes()
    p.write_bytes(original)
    c=AnalysisConfig.from_mapping({'delta':{'reference_path':str(p)}},allow_toy_reference=True)
    identity=c.analytical()
    p.unlink()
    variant=c.with_overrides({'windows':{'target_words':500}})
    assert c.analytical()==identity
    assert variant.reference_bytes==original
    assert variant.reference_sha256==c.reference_sha256


def test_pelt_product_minimum_eight_windows():
    with pytest.raises(InputError):
        AnalysisConfig.from_mapping({'changes':{'minimum_windows':7}})
def test_required_analysis_formats_are_explicit():
    import pytest
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.errors import InputError
    with pytest.raises(InputError):
        AnalysisConfig.from_mapping({'report': {'formats': ['json']}})
