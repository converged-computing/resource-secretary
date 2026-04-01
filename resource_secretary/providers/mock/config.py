import random

from resource_secretary.utils.words import *


class MockConfig:
    """
    Config for a mock worker.
    Provides a stable seed and system-wide identity.
    """

    def __init__(self, seed: int, archetype, default_target="scale"):
        self.seed = seed
        self.archetype = archetype

        # Shared random state for system-wide traits
        self.rng = random.Random(seed)

        # Generate a unique, deterministic name for this worker
        self.system_name = self.generate_name()

        # These are targets - worker character based on archetype's distribution
        # E.g., an HPC cluster will have a higher mean (between 0 and 1) for scale to sample from.
        self.generate_targets()
        self.default_target = default_target
        assert self.default_target in self.targets

    def generate_targets(self):
        """
        Generate targets for different kinds of needs.

        scale: is generally the size of something, big vs. small. HPC nodes --> scale
        density: is generally the diversity and variety. E.g., software on HPC --> high density
        """
        a = self.archetype
        self.targets = {
            "scale": self.clip(self.rng.gauss(a.mu_scale, a.sigma_scale)),
            "density": self.clip(self.rng.gauss(a.mu_density, a.sigma_density)),
        }

    def clip(self, val: float) -> float:
        return max(0.01, min(1.0, val))

    def generate_name(self) -> str:
        """
        Generate a name for the system based on archtype.
        """
        rng = random.Random(self.seed)

        # Pick an adjective
        adj = rng.choice(ADJECTIVES)

        # Pick a noun based on archetype
        if self.archetype == "hpc":
            noun = rng.choice(HPC_NOUNS)
            suffix = rng.choice(["cluster", "grid", "hpc", "center", "super"])
        elif self.archetype == "cloud":
            noun = rng.choice(CLOUD_NOUNS)
            suffix = rng.choice(["aws", "vpc", "zone", "region", "cloud"])
        else:
            noun = rng.choice(STANDALONE_NOUNS)
            suffix = rng.choice(["node", "local", "dev", "sys", "01"])

        # e.g., "abyssal-titan-cluster" / "neon-logic-vpc"
        return f"{adj}-{noun}-{suffix}"

    def get_rng(self, salt: str):
        """
        Standard seeded random number generator for providers.
        The salt should be the worker ID that uses it.
        """
        return random.Random(f"{self.seed}-{salt}")
