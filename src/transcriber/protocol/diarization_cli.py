"""Public Diarization command and event boundary values (Protocol)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

type DiarizationStage = Literal['validate', 'nemotron', 'community1', 'fusion', 'mask', 'publish']
type DiarizationFailureStage = DiarizationStage | Literal['cancelled']


@dataclass(frozen=True, slots=True)
class DiarizationCommand:
    task_work_directory: Path
    nemo_gpu_index: int = 0
    vulkan_gpu_index: int = 0

    def __post_init__(self) -> None:
        if type(self.nemo_gpu_index) is not int or self.nemo_gpu_index < -1:
            raise ValueError("nemo GPU index must be an integer >= -1")
        if type(self.vulkan_gpu_index) is not int or self.vulkan_gpu_index < 0:
            raise ValueError("Vulkan GPU index must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class DiarizationProgress:
    stage: DiarizationStage


@dataclass(frozen=True, slots=True)
class DiarizationWarning:
    reason: str


@dataclass(frozen=True, slots=True)
class DiarizationSuccess:
    diarization: Path


@dataclass(frozen=True, slots=True)
class DiarizationFailure:
    stage: DiarizationFailureStage
    message: str
