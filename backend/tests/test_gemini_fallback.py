import asyncio

import pytest

import investigator


@pytest.mark.parametrize('status,expected_models', [
    (200, ['primary']), (503, ['primary', 'backup']),
    (429, ['primary', 'backup']), (403, ['primary']),
])
def test_gemini_routes_eligible_failures_with_the_original_context(monkeypatch, status, expected_models):
    calls = []
    payload = {'sources': ['first source', 'last source']}
    schema = object()
    monkeypatch.setattr(investigator, 'MODEL', 'primary')
    monkeypatch.setattr(investigator, 'BACKUP_MODEL', 'backup')

    async def generate(system, body, schema_arg, *, model, attempts=1):
        assert system == 'original instructions' and body is payload and schema_arg is schema
        calls.append(model)
        if model == 'primary' and status != 200:
            raise investigator.ModelError(f'Gemini returned HTTP {status}; test')
        return 'validated result', {}

    monkeypatch.setattr(investigator, '_generate_gemini', generate)
    operation = investigator.generate('original instructions', payload, schema)
    if status == 403:
        with pytest.raises(investigator.ModelError):
            asyncio.run(operation)
    else:
        result, usage = asyncio.run(operation)
        assert result == 'validated result' and usage['model'] == expected_models[-1]
    assert calls == expected_models


def test_historical_ollama_assessments_cannot_enable_financial_actions():
    from autonomous_resolution import decision
    from test_autonomous_resolution import example

    case, policy, detail, records = example()
    case['analysis']['generation_providers'] = [{'provider': 'Ollama', 'model': 'historical'}]
    assert decision(case, policy, detail, records, 'MERCHANT', [])['reason'] == 'local_model_financial_execution_not_enabled'
