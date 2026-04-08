import random


class BaseArchetype:
    name = "base"

    # Defaults (between 0 and 1) to inform Gaussian selection
    # E.g., an HPC workload manager might be selecting nodes. It chooses a mean between 800 and 8000.
    # That mean is at 0.5 of the distribution, if we consider between 0 and 1
    mu_scale = 0.5
    sigma_scale = 0.2
    mu_density = 0.5
    sigma_density = 0.2

    ranges = {
        "nodes": (0, 10000),
        "cpus_per_node": (2, 128),
        "mem_per_node_gb": (2, 1024),
        "gpus_per_node": (0, 8),
        "software_packages": (0, 500),
        "partitions": (0, 100),
        "storage_gb": (10, 10000000),
    }

    def generate_physical_value(self, key: str, target: float, rng: random.Random) -> int:
        """
        Maps a normalized target (0.01-1.0) to a physical range
        defined in this archetype.
        """
        if key not in self.ranges:
            return 0

        min_v, max_v = self.ranges[key]

        # Calculate the mean (mu) based on the worker's target
        mu = min_v + (target * (max_v - min_v))

        # Jitter: 5% of the total range
        sigma = (max_v - min_v) * 0.05

        # Gaussian Sample & Clip
        val = rng.gauss(mu, sigma)
        return int(max(min_v, min(max_v, val)))


class HPCArchetype(BaseArchetype):
    name = "hpc"

    # HPC clusters tend to be large
    mu_scale = 0.7

    # HPC clusters tend to be complex
    mu_density = 0.8

    ranges = {
        "nodes": (100, 10000),
        "cpus_per_node": (32, 128),
        "mem_per_node_gb": (128, 1024),
        "gpus_per_node": (0, 8),
        "software_packages": (50, 500),
        "partitions": (3, 10),
        "storage_gb": (10000, 10000000),
    }

    slots = {
        "workload": {"min": 1, "max": 1, "choices": ["MockSlurmProvider", "MockFluxProvider"]},
        "software": {
            "min": 1,
            "max": 3,
            "choices": [
                "MockSpackProvider",
                "MockModuleProvider",
                "MockCondaProvider",
                "MockCondaProvider",
            ],
        },
        "storage": {
            "min": 1,
            "max": 2,
            "choices": ["MockLustreProvider", "MockNFSProvider"],
        },
        "container": {
            "min": 0,
            "max": 2,
            "choices": ["MockSingularityProvider", "MockPodmanProvider"],
        },
        "network": {
            "min": 1,
            "max": 1,
            "choices": ["MockInfinibandProvider", "MockOmniPathProvider"],
        },
        "hardware": {"min": 1, "max": 1, "choices": ["MockHardwareProvider"]},
        "parallel": {"min": 1, "max": 2, "choices": ["MockMPICHProvider", "MockOpenMPIProvider"]},
    }


class CloudArchetype(BaseArchetype):
    name = "cloud"
    mu_scale = 0.3
    mu_density = 0.4

    ranges = {
        "nodes": (1, 500),
        "cpus_per_node": (2, 64),
        "mem_per_node_gb": (4, 256),
        "gpus_per_node": (0, 4),
        "software_packages": (10, 50),
        "partitions": (1, 3),
        "storage_gb": (10, 5000),
    }

    slots = {
        "workload": {"min": 1, "max": 1, "choices": ["MockKubernetesProvider"]},
        "software": {"min": 1, "max": 1, "choices": ["MockCondaProvider", "MockPipProvider"]},
        "storage": {"min": 1, "max": 2, "choices": ["MockS3Provider", "MockNFSProvider"]},
        "network": {"min": 1, "max": 1, "choices": ["MockEthernetProvider"]},
        "hardware": {"min": 1, "max": 1, "choices": ["MockHardwareProvider"]},
        "container": {"min": 0, "max": 1, "choices": ["MockDockerProvider"]},
    }


class StandaloneArchetype(BaseArchetype):
    name = "standalone"

    # A standalone service / FaaS / VM / edge-device is just one node
    ranges = {
        "nodes": (1, 1),
        "cpus_per_node": (4, 32),
        "mem_per_node_gb": (8, 128),
        "gpus_per_node": (0, 1),
        "software_packages": (20, 100),
        "storage_gb": (100, 2000),
    }

    # Cardinality for each type.
    slots = {
        "workload": {"min": 1, "max": 1, "choices": ["MockMachineProvider"]},
        "software": {"min": 1, "max": 2, "choices": ["MockCondaProvider", "MockPipProvider"]},
        "storage": {"min": 1, "max": 1, "choices": ["MockLocalScratchProvider"]},
        "hardware": {"min": 1, "max": 1, "choices": ["MockHardwareProvider"]},
        "network": {"min": 1, "max": 1, "choices": ["MockEthernetProvider"]},
        "container": {
            "min": 0,
            "max": 2,
            "choices": ["MockDockerProvider", "MockSingularityProvider"],
        },
    }
