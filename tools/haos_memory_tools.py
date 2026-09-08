"""HAOS Memory Tools: Obsidian Vault (ADRs/especificações) & GraphRAG (entidades/relacionamentos).

Registra as ferramentas de memória canônica e relacional do HAOS para o agente.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_home
from tools.registry import registry


def _get_obsidian_adapter():
    home = Path(get_hermes_home())
    vault = home / "vault"
    if not vault.exists():
        vault.mkdir(parents=True, exist_ok=True)
        adrs = vault / "adrs"
        adrs.mkdir(parents=True, exist_ok=True)
    from hermes.platform.memory.obsidian import ObsidianAdapter
    return ObsidianAdapter(str(vault))


def _get_graphrag_client():
    home = Path(get_hermes_home())
    gr_dir = home / "graphrag"
    if not gr_dir.exists():
        gr_dir.mkdir(parents=True, exist_ok=True)
    from hermes.platform.memory.graphrag import GraphRAGClient
    return GraphRAGClient(index_dir=str(gr_dir))


def obsidian_get_adr(adr_id: str) -> str:
    """Busca uma ADR (Architecture Decision Record) no Obsidian Vault."""
    try:
        adapter = _get_obsidian_adapter()
        if not adapter.available():
            return json.dumps({"error": "Obsidian Vault não disponível"})
        content = adapter.get_adr(adr_id)
        if content is None:
            return json.dumps({"found": False, "message": f"ADR '{adr_id}' não encontrada"})
        return json.dumps({"found": True, "adr_id": adr_id, "content": content})
    except Exception as e:
        return json.dumps({"error": str(e)})


def obsidian_save_note(title: str, content: str, folder: str = "") -> str:
    """Salva uma nota ou ADR no Obsidian Vault canônico."""
    try:
        home = Path(get_hermes_home())
        vault = home / "vault"
        target_dir = vault / folder if folder else vault
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{title}.md" if not title.endswith(".md") else title
        note_path = target_dir / filename
        note_path.write_text(content, encoding="utf-8")
        return json.dumps({"success": True, "path": str(note_path)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def graphrag_query(query: str, mode: str = "global") -> str:
    """Consulta o grafo de entidades e relacionamentos do GraphRAG."""
    try:
        client = _get_graphrag_client()
        if not client.available():
            return json.dumps({"error": "GraphRAG índice local não disponível"})
        if mode == "local":
            res = client.query_local(query)
        else:
            res = client.query_global(query)
        return json.dumps({"success": True, "results": res})
    except Exception as e:
        return json.dumps({"error": str(e)})


registry.register(
    name="obsidian_get_adr",
    toolset="memory",
    schema={
        "name": "obsidian_get_adr",
        "description": "Recupera uma ADR (Architecture Decision Record) canônica do Obsidian Vault pelo ID (ex: 'ADR-001').",
        "parameters": {
            "type": "object",
            "properties": {
                "adr_id": {"type": "string", "description": "ID da ADR, ex: 'ADR-001'"}
            },
            "required": ["adr_id"],
        },
    },
    handler=lambda args, **kw: obsidian_get_adr(args.get("adr_id", "")),
)

registry.register(
    name="obsidian_save_note",
    toolset="memory",
    schema={
        "name": "obsidian_save_note",
        "description": "Grava uma nova nota de arquitetura, especificação ou ADR no Obsidian Vault canônico.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título da nota ou arquivo (ex: 'ADR-002-novo-modulo')"},
                "content": {"type": "string", "description": "Conteúdo Markdown da nota"},
                "folder": {"type": "string", "description": "Subpasta dentro do vault, padrão vazio ou 'adrs'"}
            },
            "required": ["title", "content"],
        },
    },
    handler=lambda args, **kw: obsidian_save_note(
        title=args.get("title", ""),
        content=args.get("content", ""),
        folder=args.get("folder", "")
    ),
)

registry.register(
    name="graphrag_query",
    toolset="memory",
    schema={
        "name": "graphrag_query",
        "description": "Consulta o grafo de conhecimento GraphRAG para encontrar entidades, componentes e seus relacionamentos.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca ou entidade a consultar (ex: 'Kanban', 'HAOS')"},
                "mode": {"type": "string", "enum": ["global", "local"], "description": "Modo de consulta (global ou local)"}
            },
            "required": ["query"],
        },
    },
    handler=lambda args, **kw: graphrag_query(
        query=args.get("query", ""),
        mode=args.get("mode", "global")
    ),
)
