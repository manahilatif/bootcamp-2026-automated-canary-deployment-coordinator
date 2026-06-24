import logging
import config
import cluster as cluster_module
import rollout
import abort

def run_deployment():
    cluster_module.initialize_cluster()
    abort.start_abort_listener()
    
    logging.info("=== DEPLOYMENT STARTED ===")
    cluster_module.print_cluster_state()

    # Stage 1 — update 10%
    logging.info("--- Stage 1: Updating 10% of servers ---")
    rollout.update_servers(config.STAGE_1_PERCENT)
    
    if abort.is_aborted():
        rollout.rollback()
        return

    aborted = abort.interruptible_sleep(config.SLEEP_STAGE_1)
    if aborted:
        rollout.rollback()
        return

    # Analysis 1
    passed = rollout.analyze()
    if not passed or abort.is_aborted():
        rollout.rollback()
        return

    # Stage 2 — update 50%
    logging.info("--- Stage 2: Updating 50% of servers ---")
    rollout.update_servers(config.STAGE_2_PERCENT)

    if abort.is_aborted():
        rollout.rollback()
        return

    aborted = abort.interruptible_sleep(config.SLEEP_STAGE_2)
    if aborted:
        rollout.rollback()
        return

    # Final analysis
    passed = rollout.analyze()
    if not passed or abort.is_aborted():
        rollout.rollback()
        return

    # Stage 3 — update remaining
    logging.info("--- Stage 3: Updating remaining servers ---")
    rollout.update_servers(1.0)

    if abort.is_aborted():
        rollout.rollback()
        return

    logging.info("=== DEPLOYMENT COMPLETE ===")
    cluster_module.print_cluster_state()

if __name__ == "__main__":
    run_deployment()