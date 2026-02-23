"""Outil — Informations système."""

import logging
import os
import platform
import shutil

log = logging.getLogger(__name__)


class SystemInfoTool:
    """Fournit des informations sur le système (OS, mémoire, etc.)."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return (
            "Retourne des informations sur le système : OS, processeur, "
            "mémoire disponible, espace disque. Utilise cet outil quand "
            "l'utilisateur demande des infos sur son ordinateur ou son système."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self) -> str:
        """Collecte et retourne les infos système."""
        info_parts = []

        # OS
        info_parts.append(
            f"Systeme: {platform.system()} {platform.release()} ({platform.machine()})"
        )

        # Processeur
        proc = platform.processor()
        if proc:
            info_parts.append(f"Processeur: {proc}")

        # Mémoire (si psutil disponible)
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            avail_gb = mem.available / (1024 ** 3)
            info_parts.append(
                f"Memoire: {avail_gb:.1f} Go disponibles sur {total_gb:.1f} Go "
                f"({mem.percent}% utilise)"
            )
        except ImportError:
            pass

        # Espace disque (utiliser le disque système sur Windows)
        try:
            disk_root = os.environ.get("SystemDrive", "C:") + "\\"
            disk = shutil.disk_usage(disk_root)
            total_gb = disk.total / (1024 ** 3)
            free_gb = disk.free / (1024 ** 3)
            used_pct = (disk.used / disk.total) * 100
            info_parts.append(
                f"Disque ({disk_root}): {free_gb:.1f} Go libres sur {total_gb:.1f} Go "
                f"({used_pct:.0f}% utilise)"
            )
        except Exception:
            pass

        # GPU (si torch disponible)
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                # mem_get_info retourne (free, total) depuis le driver CUDA
                vram_free, vram_total = torch.cuda.mem_get_info(0)
                vram_free_gb = vram_free / (1024 ** 3)
                vram_total_gb = vram_total / (1024 ** 3)
                info_parts.append(
                    f"GPU: {gpu_name} ({vram_free_gb:.1f} Go VRAM libres "
                    f"sur {vram_total_gb:.1f} Go)"
                )
        except (ImportError, AttributeError):
            pass

        return ". ".join(info_parts) + "."
