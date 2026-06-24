import config

cluster = []

def initialize_cluster():
    global cluster
    cluster = [
        {
            "id": i,
            "version": config.OLD_VERSION,
            "status": "healthy"
        }
        for i in range(1, config.TOTAL_SERVERS + 1)
    ]

def get_cluster():
    return cluster

def print_cluster_state():
    version_counts = {}
    for server in cluster:
        v = server["version"]
        version_counts[v] = version_counts.get(v, 0) + 1

    print("Cluster State:")
    for version, count in version_counts.items():
        print(f"  {version}: {count} servers")

    status_counts = {}        # ← this line must exist
    for server in cluster:
        s = server["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    for status, count in status_counts.items():
        print(f"  {status}: {count} servers")
    print()