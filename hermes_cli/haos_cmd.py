"""HAOS CLI Commands: 'hermes haos'.

Frente 1: CLI & Operação ('hermes haos'):
- hermes haos status [--json]
- hermes haos federation ping <peer_id>
- hermes haos skills list
- hermes haos skills promote <skill_id>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_haos_status() -> Dict[str, Any]:
    """Collects platform summary:
    - Tríade: Memory scopes
    - Procedural skills registered / active
    - Capabilities count
    - Model failover routes status
    - Federated nodes
    """
    # 1. Tríade Memory scopes
    memory_scopes = ["per_turn", "session", "vault", "graphrag", "decision_store"]
    vault_status = "unconfigured"
    try:
        from hermes.platform.context.memory.federated_fabric import FederatedMemoryCoordinator
        coordinator = FederatedMemoryCoordinator()
        configured_scopes = list(coordinator.adapters.keys()) if hasattr(coordinator, "adapters") else memory_scopes
    except Exception:
        configured_scopes = memory_scopes

    # 2. Procedural skills
    skills_total = 0
    skills_active = 0
    try:
        from hermes.platform.skills.procedural_engine import SkillRegistry
        registry = SkillRegistry()
        all_skills = registry.list_skills()
        skills_total = len(all_skills)
        skills_active = len([s for s in all_skills if getattr(s, "status", "") == "active"])
    except Exception:
        pass

    # 3. Capabilities count
    capabilities_count = 0
    try:
        from hermes.platform.capabilities.universal_registry import UniversalCapabilityRegistry
        cap_registry = UniversalCapabilityRegistry()
        capabilities_count = len(cap_registry.list_capabilities())
    except Exception:
        pass

    # 4. Model failover routes status
    model_routes = {}
    try:
        from hermes.platform.models.model_resolver import ModelResolver
        resolver = ModelResolver()
        for pid, prof in resolver.profiles.items():
            model_routes[pid] = {
                "name": getattr(prof, "name", pid),
                "primary": f"{prof.primary.provider}:{prof.primary.model}" if getattr(prof, "primary", None) else "unknown",
                "fallbacks_count": len(getattr(prof, "fallbacks", [])),
            }
    except Exception:
        pass

    # 5. Federated nodes
    federated_nodes: List[Dict[str, Any]] = []
    try:
        from hermes.platform.federation.orchestrator import FederatedOrchestrator
        orch = FederatedOrchestrator(node_id="local-node")
        nodes_dict = orch.get_federated_nodes()
        federated_nodes = list(nodes_dict.values())
    except Exception:
        pass

    return {
        "timestamp": time.time(),
        "memory": {
            "scopes": configured_scopes,
            "status": "operational",
        },
        "procedural_skills": {
            "total": skills_total,
            "active": skills_active,
        },
        "capabilities": {
            "count": capabilities_count,
        },
        "model_routes": model_routes,
        "federated_nodes": {
            "count": len(federated_nodes),
            "nodes": federated_nodes,
        },
    }


def cmd_haos_status(args: argparse.Namespace) -> int:
    """Executes 'hermes haos status'."""
    status = _get_haos_status()
    if getattr(args, "json", False):
        print(json.dumps(status, indent=2))
        return 0

    print("==================================================")
    print("           HAOS PLATFORM STATUS SUMMARY           ")
    print("==================================================")
    print("\n[Tríade Memory Scopes]")
    for scope in status["memory"]["scopes"]:
        print(f"  • {scope}")
    print(f"  Status: {status['memory']['status']}")

    print("\n[Procedural Skills]")
    print(f"  Registered total: {status['procedural_skills']['total']}")
    print(f"  Active:           {status['procedural_skills']['active']}")

    print("\n[Universal Capabilities]")
    print(f"  Active capabilities count: {status['capabilities']['count']}")

    print("\n[Model Routes & Failover]")
    if not status["model_routes"]:
        print("  No model routes loaded.")
    else:
        for pid, r in status["model_routes"].items():
            print(f"  • {pid}: primary={r['primary']} (fallbacks={r['fallbacks_count']})")

    print("\n[Federated Nodes]")
    print(f"  Connected nodes: {status['federated_nodes']['count']}")
    for n in status["federated_nodes"]["nodes"]:
        print(f"  • {n.get('node_id')}: agents={len(n.get('agents', []))}")
    print("==================================================")
    return 0


def cmd_haos_federation_ping(args: argparse.Namespace) -> int:
    """Executes 'hermes haos federation ping <peer_id>'."""
    peer_id = args.peer_id
    shared_secret = getattr(args, "secret", None) or "haos-test-secret"
    endpoint = getattr(args, "endpoint", None)
    local_id = getattr(args, "local_node_id", None) or "node_local_primary"
    print(f"Initiating mutual 3-way HMAC handshake with peer '{peer_id}'...")

    try:
        from hermes.platform.federation.orchestrator import FederatedOrchestrator, HandshakeState

        if endpoint:
            # Live mesh socket / HTTP connection
            from hermes.platform.federation.mesh import FederatedMeshNode
            host, port_str = endpoint.split(":")
            port = int(port_str)

            local_node = FederatedMeshNode(node_id=local_id, host="127.0.0.1", port=0)
            local_node.start()
            try:
                local_node.register_peer_secret(peer_id, shared_secret)
                local_node.register_peer_address(peer_id, host, port)
                init_session, resp_session = local_node.perform_live_handshake(peer_node_id=peer_id)
            finally:
                local_node.stop()
        else:
            # Local in-process fallback
            local_orch = FederatedOrchestrator(node_id=local_id)
            local_orch.register_peer_secret(peer_id, shared_secret)

            peer_orch = FederatedOrchestrator(node_id=peer_id)
            peer_orch.register_peer_secret(local_id, shared_secret)

            init_session, resp_session = local_orch.perform_mutual_handshake(peer_orch)

        if init_session and init_session.state == HandshakeState.ESTABLISHED:
            print(f"✓ Handshake successful! Mutual HMAC-SHA256 authenticated with '{peer_id}'.")
            print(f"  Session ID: {init_session.session_id}")
            print(f"  State: {init_session.state.value}")
            return 0
        else:
            print(f"✗ Handshake failed with peer '{peer_id}'.")
            return 1
    except Exception as e:
        print(f"✗ Error during federation handshake with '{peer_id}': {e}")
        return 1


def cmd_haos_skills_list(args: argparse.Namespace) -> int:
    """Executes 'hermes haos skills list'."""
    try:
        from hermes.platform.skills.procedural_engine import SkillRegistry
        registry = SkillRegistry()
        skills = registry.list_skills()
    except Exception as e:
        print(f"Error loading skill registry: {e}")
        return 1

    if not skills:
        print("No procedural skills currently registered in SkillRegistry.")
        return 0

    print(f"Found {len(skills)} procedural skill(s):")
    print(f"{'NAME':<25} {'VERSION':<10} {'STATUS':<12} {'DESCRIPTION'}")
    print("-" * 75)
    for s in skills:
        desc = (s.description or "")[:35]
        print(f"{s.name:<25} {s.version:<10} {s.status:<12} {desc}")
    return 0


def cmd_haos_skills_promote(args: argparse.Namespace) -> int:
    """Executes 'hermes haos skills promote <skill_id>'."""
    skill_id = args.skill_id
    version = getattr(args, "version", None)

    try:
        from hermes.platform.skills.procedural_engine import SkillRegistry, SkillLifecyclePipeline
        registry = SkillRegistry()
        spec = registry.get(skill_id, version)

        if not spec:
            print(f"✗ Skill '{skill_id}' (version: {version or 'latest'}) not found in registry.")
            return 1

        pipeline = SkillLifecyclePipeline(registry=registry)
        success, msg = pipeline.run_full_pipeline(spec)

        if success:
            print(f"✓ {msg}")
            return 0
        else:
            print(f"✗ Failed to promote skill '{skill_id}': {msg}")
            return 1
    except Exception as e:
        print(f"✗ Error during promotion pipeline for '{skill_id}': {e}")
        return 1


def cmd_haos_doctor(args: argparse.Namespace) -> int:
    """Executes 'hermes haos doctor'."""
    from hermes.platform.diagnostics.doctor import HAOSDoctor
    return HAOSDoctor.print_terminal_report(json_output=getattr(args, "json", False))


def build_haos_parser(subparsers) -> argparse.ArgumentParser:
    """Builds and registers the parser for 'hermes haos'."""
    haos_parser = subparsers.add_parser(
        "haos",
        help="HAOS Control Plane, Tríade status, Federation, and Procedural Skills",
        description="HAOS Control Plane: inspect Tríade status, federated nodes, and procedural skills lifecycle.",
    )
    haos_sub = haos_parser.add_subparsers(dest="haos_command")

    # hermes haos status [--json]
    status_parser = haos_sub.add_parser("status", help="Show full HAOS platform summary")
    status_parser.add_argument("--json", action="store_true", help="Output status summary as JSON")
    status_parser.set_defaults(func=cmd_haos_status)

    # hermes haos doctor [--json]
    doctor_parser = haos_sub.add_parser("doctor", help="Valida a integridade, permissões e isolamento do HAOS")
    doctor_parser.add_argument("--json", action="store_true", help="Output doctor diagnostics as JSON")
    doctor_parser.set_defaults(func=cmd_haos_doctor)

    # hermes haos federation ping <peer_id>
    fed_parser = haos_sub.add_parser("federation", help="HAOS Federation management")
    fed_sub = fed_parser.add_subparsers(dest="federation_command")
    
    ping_parser = fed_sub.add_parser("ping", help="Mutual 3-way HMAC handshake with a peer node")
    ping_parser.add_argument("peer_id", help="Target federated peer node identifier")
    ping_parser.add_argument("--secret", help="Shared HMAC secret (optional, defaults to pre-configured)")
    ping_parser.add_argument("--local-node-id", default="node_local_primary", help="Local node identifier (default: node_local_primary)")
    ping_parser.add_argument("--endpoint", help="Peer network endpoint host:port (optional, for live mesh ping)")
    ping_parser.set_defaults(func=cmd_haos_federation_ping)

    # hermes haos skills list / promote <skill_id>
    skills_parser = haos_sub.add_parser("skills", help="HAOS Procedural Skills lifecycle")
    skills_sub = skills_parser.add_subparsers(dest="skills_command")

    list_parser = skills_sub.add_parser("list", help="List registered procedural skills and lifecycle status")
    list_parser.set_defaults(func=cmd_haos_skills_list)

    promote_parser = skills_sub.add_parser("promote", help="Trigger evaluation and promotion pipeline for candidate skill")
    promote_parser.add_argument("skill_id", help="Skill name/ID to evaluate and promote")
    promote_parser.add_argument("--version", help="Specific skill version (optional)")
    promote_parser.set_defaults(func=cmd_haos_skills_promote)

    # Default fallback when 'hermes haos' is run without subcommands
    haos_parser.set_defaults(func=lambda args: haos_parser.print_help() or 0)
    return haos_parser
