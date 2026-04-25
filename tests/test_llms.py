import pytest


def _import_llms_or_skip():
    try:
        import llms  # type: ignore
        return llms
    except Exception as exc:
        pytest.skip(f"Skipping: unable to import llms module: {exc}")


def test_generate_json_uses_local_model_unless_openai_is_explicit(add_web_to_syspath, monkeypatch):
    llms_module = _import_llms_or_skip()
    monkeypatch.setattr(llms_module, 'OPENAI_API_KEY', 'env-key')
    monkeypatch.setattr(
        llms_module,
        '_post_ollama_generate',
        lambda payload, timeout_seconds=None: (True, {'response': '{"ok": true}'}, None),
    )

    def _fail_openai(*args, **kwargs):
        raise AssertionError('OpenAI should not be used without explicit opt-in')

    monkeypatch.setattr(llms_module, '_post_openai_chat', _fail_openai)

    result = llms_module.generate_json('return {"ok": true}', use_openai=False)

    assert result['success'] is True
    assert result['data'] == {'ok': True}
