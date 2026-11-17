"""Environment discovery shared by wizard step 4 and `manage.py connect_proxmox`."""

import json
import logging

from apps.wizard.models import DiscoveredEnvironment

logger = logging.getLogger(__name__)


def run_discovery(config):
    """Read nodes, storage, networks, VMIDs and CPU model from Proxmox.

    Saves a DiscoveredEnvironment and moves the wizard to step 5 at least.
    Raises ProxmoxAPIError (or any other exception) on failure.
    """
    api = config.get_api_client()
    nodes = api.get_nodes()

    node_name = nodes[0]["node"] if nodes else config.default_node or "pve"

    storage_raw = api.get_storage(node_name)
    networks_raw = api.get_networks(node_name)
    vms = api.get_vms(node_name)
    existing_vmids = [int(vm["vmid"]) for vm in vms if "vmid" in vm]

    storage_pools = []
    for s in storage_raw:
        avail = s.get("avail", 0) or 0
        s["avail_gb"] = avail / 1024 / 1024 / 1024
        s["shared"] = bool(s.get("shared", 0))
        storage_pools.append(s)

    network_bridges = [
        n["iface"] for n in networks_raw
        if n.get("type") in ("bridge", "bond", "eth", "vlan") or n["iface"].startswith("vmbr")
    ]
    if not network_bridges:
        network_bridges = [n["iface"] for n in networks_raw]

    cpu_info = ""
    try:
        with config.get_ssh_client() as ssh:
            stdout, _stderr, _rc = ssh.run(["grep", "model name", "/proc/cpuinfo"])
            for line in stdout.splitlines():
                if "model name" in line:
                    cpu_info = line.split(":", 1)[-1].strip()
                    break
    except Exception as ssh_exc:
        logger.warning("discovery: SSH CPU info failed: %s", ssh_exc)
        cpu_info = "Unknown (SSH not available)"

    env, _created = DiscoveredEnvironment.objects.get_or_create(config=config)
    env.nodes_json = json.dumps(nodes)
    env.storage_json = json.dumps(storage_raw)
    env.networks_json = json.dumps(networks_raw)
    env.host_cpu_info = cpu_info[:500]
    env.existing_vmids_json = json.dumps(existing_vmids)
    env.save()

    config.wizard_step = max(config.wizard_step, 5)
    config.save()

    return {
        "nodes": nodes,
        "storage_pools": storage_pools,
        "network_bridges": network_bridges,
        "cpu_info": cpu_info,
        "existing_vmids": existing_vmids,
    }
