from __future__ import annotations

from dataclasses import dataclass

from .system import SystemInfo

LOW = "low"
MEDIUM = "medium"
MAX = "max"
AUTO = "auto"
PROFILES = {LOW, MEDIUM, MAX}


@dataclass(frozen=True)
class ModelCandidate:
    model: str
    profile: str
    note: str
    disk_gb: float


def model_candidates(system_info: SystemInfo) -> list[ModelCandidate]:
    return list(profile_models(system_info).values())


def profile_models(system_info: SystemInfo) -> dict[str, ModelCandidate]:
    ram = system_info.ram_gb
    machine = system_info.machine.lower()
    apple_silicon = system_info.os_name == "Darwin" and ("arm" in machine or "aarch" in machine)

    if ram < 16:
        return {
            LOW: ModelCandidate("qwen2.5-coder:7b", LOW, "smallest MiniDev local coding fallback", 4.7),
            MEDIUM: ModelCandidate("qwen3:4b-instruct", MEDIUM, "small instruct model with better OpenCode context fit", 2.5),
            MAX: ModelCandidate("qwen3:4b-instruct", MAX, "best MiniDev agent model for low-memory devices", 2.5),
        }

    if ram <= 32:
        max_model = "qwen3:4b-instruct" if apple_silicon else "qwen2.5-coder:14b"
        max_disk_gb = 2.5 if apple_silicon else 9.0
        return {
            LOW: ModelCandidate("qwen2.5-coder:7b", LOW, "fastest local fallback for battery or memory pressure", 4.7),
            MEDIUM: ModelCandidate("qwen2.5-coder:14b", MEDIUM, "balanced local coding model", 9.0),
            MAX: ModelCandidate(
                max_model,
                MAX,
                "instruct model with reliable context fit for OpenCode on 16GB Macs" if apple_silicon else "best local coding model for this device",
                max_disk_gb,
            ),
        }

    return {
        LOW: ModelCandidate("qwen2.5-coder:14b", LOW, "fast local fallback", 9.0),
        MEDIUM: ModelCandidate("qwen2.5-coder:32b", MEDIUM, "larger dense local coding model", 20.0),
        MAX: ModelCandidate("qwen3:30b-a3b", MAX, "MoE local model with advertised tools/thinking support", 19.0),
    }


def pick_preferred_model(system_info: SystemInfo) -> str:
    return profile_models(system_info)[MAX].model


def pick_profile_model(system_info: SystemInfo, profile: str) -> str:
    normalized = profile.lower()
    if normalized == AUTO:
        normalized = MAX
    if normalized not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    return profile_models(system_info)[normalized].model
