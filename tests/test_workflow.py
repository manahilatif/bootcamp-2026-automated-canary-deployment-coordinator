import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config
import workflow as workflow_module


def test_workflow_rolls_back_after_stage_1_analysis_failure(monkeypatch):
    calls = []

    async def fake_execute_activity(activity_fn, *args, **kwargs):
        calls.append((activity_fn.__name__, args))
        if activity_fn is workflow_module.analyze_activity:
            return False
        if activity_fn is workflow_module.update_servers_activity:
            return 2
        return None

    async def fake_sleep(_duration):
        return None

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(workflow_module.workflow, "sleep", fake_sleep)

    result = asyncio.run(workflow_module.CanaryRolloutWorkflow().run())

    assert result == "ROLLED BACK after Stage 1 analysis"
    assert calls == [
        ("initialize_cluster_activity", ()),
        ("update_servers_activity", (config.STAGE_1_PERCENT,)),
        ("analyze_activity", ()),
        ("rollback_activity", ()),
    ]
