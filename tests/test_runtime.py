from src.runtime import SessionRuntime


def test_session_reuses_same_gateway_and_loop(settings):
    runtime=SessionRuntime()
    try:
        def run():
            return list(runtime.iter_events(settings,True,"hello","gpt-4o-mini",.7,64))
        first=run()
        gateway=runtime._gateway
        second=run()
        assert runtime._gateway is gateway
        assert sum(v.is_final for k,v in first if k=="chunk")==1
        assert sum(v.is_final for k,v in second if k=="chunk")==1
        assert runtime.alive
    finally:
        runtime.close()
    assert not runtime.alive


def test_config_change_closes_old_gateway(settings):
    from src.security import Settings
    runtime=SessionRuntime()
    try:
        list(runtime.iter_events(settings,True,"hello","gpt-4o-mini",.7,64))
        first=runtime._gateway
        updated=Settings(openai_api_key="sk-"+"Z"*32)
        list(runtime.iter_events(updated,True,"hello","gpt-4o-mini",.7,64))
        assert runtime._gateway is not first
        assert first._closed
    finally:
        runtime.close()
