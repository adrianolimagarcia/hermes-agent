"""GitWorktreeManager — Gerenciamento de Git Worktrees Efêmeros para Isolamento na Lane Kilo.

Cria worktrees vinculados em subdiretórios efêmeros (.worktrees/task-<id>),
garantindo que execuções de Coder e Reviewer nunca colidam com o workspace principal
nem poluam a árvore de trabalho do operador.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitWorktreeError(RuntimeError):
    pass


class GitWorktreeManager:
    """Gerencia o ciclo de vida de worktrees efêmeros do Git."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            repo_root = Path(os.getcwd())
        self.repo_root = Path(repo_root).resolve()
        self.worktrees_dir = self.repo_root / ".worktrees"

    def _run_git(self, *args: str, cwd: Optional[Path] = None) -> str:
        cmd = ["git", *args]
        res = subprocess.run(
            cmd,
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise GitWorktreeError(
                f"git command failed: {' '.join(cmd)}\nstderr: {res.stderr.strip()}"
            )
        return res.stdout.strip()

    def create_worktree(
        self,
        task_id: str,
        base_branch: str = "haos-fork",
    ) -> Path:
        """Cria um worktree efêmero e uma branch dedicada para a tarefa."""
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = (self.worktrees_dir / f"task-{task_id}").resolve()
        branch_name = f"haos/task-{task_id}"

        # Se o worktree já existe, reutiliza
        if worktree_path.exists():
            return worktree_path

        # Cria worktree com branch nova baseada na base_branch
        try:
            self._run_git(
                "worktree", "add", "-b", branch_name, str(worktree_path), base_branch
            )
        except GitWorktreeError as exc:
            # Se a branch já existir, tenta vincular sem -b
            if "already exists" in str(exc):
                self._run_git(
                    "worktree", "add", str(worktree_path), branch_name
                )
            else:
                raise

        return worktree_path

    def get_diff(self, task_id: str, base_branch: str = "haos-fork") -> str:
        """Obtém o diff de alterações produzidas no worktree em relação à base."""
        branch_name = f"haos/task-{task_id}"
        return self._run_git("diff", f"{base_branch}...{branch_name}")

    def remove_worktree(self, task_id: str, force: bool = True) -> bool:
        """Remove o worktree efêmero e limpa a referência no git."""
        worktree_path = (self.worktrees_dir / f"task-{task_id}").resolve()
        if not worktree_path.exists():
            return False

        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))

        try:
            self._run_git(*args)
        except Exception:
            # Fallback seguro
            shutil.rmtree(worktree_path, ignore_errors=True)
            try:
                self._run_git("worktree", "prune")
            except Exception:
                pass
        return True

    def merge_worktree(
        self,
        task_id: str,
        target_branch: str = "haos-fork",
    ) -> str:
        """Faz merge da branch da tarefa na target branch."""
        branch_name = f"haos/task-{task_id}"
        # Garante checkout da branch alvo
        self._run_git("checkout", target_branch)
        return self._run_git("merge", branch_name, "--no-edit")
