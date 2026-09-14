from account_history_analyzer.registry import feature_registry, method_registry


def test_REG_01_contract_and_stability():
    features = feature_registry()
    required = {'feature_id', 'description', 'view', 'formula', 'unit', 'numerator', 'denominator',
                'missingness_rule', 'evidence_rule', 'version'}
    assert features
    assert all(required <= f.keys() for f in features)
    ids = [f['feature_id'] for f in features]
    assert ids == sorted(set(ids))
    first = features[0]['description']
    features[0]['description'] = 'mutated'
    assert feature_registry()[0]['description'] == first
    assert method_registry()
