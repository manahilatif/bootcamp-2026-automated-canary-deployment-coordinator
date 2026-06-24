import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
import cluster as cluster_module
import rollout

def test_update_servers_correct_count():
    cluster_module.initialize_cluster()
    rollout.update_servers(config.STAGE_1_PERCENT)
    servers = cluster_module.get_cluster()
    updated = [s for s in servers if s["version"] == config.NEW_VERSION]
    assert len(updated) == 2

def test_update_servers_only_updates_old():
    cluster_module.initialize_cluster()
    rollout.update_servers(config.STAGE_1_PERCENT)
    rollout.update_servers(config.STAGE_2_PERCENT)
    servers = cluster_module.get_cluster()
    updated = [s for s in servers if s["version"] == config.NEW_VERSION]
    assert len(updated) == 11

def test_rollback_restores_all_servers():
    cluster_module.initialize_cluster()
    rollout.update_servers(config.STAGE_1_PERCENT)
    rollout.update_servers(config.STAGE_2_PERCENT)
    rollout.rollback()
    servers = cluster_module.get_cluster()
    old = [s for s in servers if s["version"] == config.OLD_VERSION]
    assert len(old) == 20

def test_rollback_sets_status_healthy():
    cluster_module.initialize_cluster()
    rollout.update_servers(config.STAGE_1_PERCENT)
    rollout.rollback()
    servers = cluster_module.get_cluster()
    assert all(s["status"] == "healthy" for s in servers)

def test_analyze_returns_bool():
    cluster_module.initialize_cluster()
    rollout.update_servers(config.STAGE_1_PERCENT)
    result = rollout.analyze()
    assert isinstance(result, bool)