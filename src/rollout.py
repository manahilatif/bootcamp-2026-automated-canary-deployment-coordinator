import random
import math
import logging
import config
import cluster as cluster_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)

def update_servers(percentage):
    servers = cluster_module.get_cluster()
    
    eligible = [s for s in servers if s["version"] == config.OLD_VERSION]
    count = math.ceil(len(eligible) * percentage)
    to_update = eligible[:count]
    
    logging.info(f"Updating {count} servers ({int(percentage * 100)}% of eligible)...")
    
    for server in to_update:
        server["status"] = "updating"
        server["version"] = config.NEW_VERSION
        server["status"] = "healthy"
        logging.info(f"  Server {server['id']} → {config.NEW_VERSION}")
    
    cluster_module.print_cluster_state()
    return to_update

def analyze():
    logging.info("Running health analysis...")
    
    servers = cluster_module.get_cluster()
    updated = [s for s in servers if s["version"] == config.NEW_VERSION]
    
    failure_roll = random.random()
    
    if failure_roll < config.ANALYSIS_FAILURE_RATE:
        failed_server = random.choice(updated) if updated else None
        if failed_server:
            failed_server["status"] = "failed"
            logging.warning(f"  Server {failed_server['id']} failed health check")
        logging.warning("Analysis result: FAIL")
        return False
    
    logging.info("Analysis result: PASS")
    return True

def rollback():
    logging.warning("ROLLBACK INITIATED")
    servers = cluster_module.get_cluster()
    
    rolled_back = 0
    for server in servers:
        if server["version"] == config.NEW_VERSION:
            server["version"] = config.OLD_VERSION
            server["status"] = "healthy"
            rolled_back += 1
            logging.warning(f"  Server {server['id']} rolled back to {config.OLD_VERSION}")
    
    logging.warning(f"Rollback complete. {rolled_back} servers restored.")
    cluster_module.print_cluster_state()