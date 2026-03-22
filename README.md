# resource secretary

> Discover providers for resources (software, workload managers) for agentic science and beyond!

![https://github.com/converged-computing/resource-secretary/blob/main/img/resource-secretary-small.png?raw=true](https://github.com/converged-computing/resource-secretary/blob/main/img/resource-secretary-small.png?raw=true)

[![PyPI - Version](https://img.shields.io/pypi/v/resource-secretary)](https://badge.fury.io/py/resource-secretary)

## Design

We have different needs to discover resources on a system. If we have a framework with a hub and workers, it does not make sense to hard code worker types.
A worker needs to dynamically discovery different kinds of providers in an environment, whether that provider is a workload manager or software package manager.
Specifically, a worker needs to come up and do two things:

- discover hardware, and other cluster environment that does not change (or changes slowly)
- discover providers (either managers, software, or other providers of resources that will change state). For example, this is flux, slurm with queues, environment modules, etc.

There are no rules about what a cluster is allowed to have. If a cluster is found to have flux AND slurm that is entirely valid!
The interaction for [job negotiation](https://gist.github.com/vsoch/ba0fd119e12ff75dcbdec85e12703e43) proceeds as before. But instead of a single hard coded ask to secretary we have an interaction where the prompt still comes in with a specific resource request and policy, however the secretary agent needs a way to query its providers, or ask questions.

### Tools (classes) for discovery

The insight that I had is that these are different classes, and the classes need to work akin to mcp servers that provide tools, but the tools are functions. So for example this structure:

```console
resource_secretary/providers/
├── container
│   ├── charliecloud.py
│   ├── oci.py          # includes docker and podman
│   ├── shifter.py
│   └── singularity.py  # includes podman and singularity
├── hardware
│   ├── amd.py
│   ├── cpu.py
│   ├── gpu.py
│   ├── memory.py
│   └── nvidia.py
├── network
│   ├── ethernet.py
│   ├── infiniband.py
│   ├── network.py
│   └── omnipath.py
├── parallel
│   ├── mpich.py
│   ├── openmpi.py
│   └── spectrum.py
├── provider.py
├── software
│   ├── modules.py      # includes lmod and environment modules
│   └── spack.py
├── storage
│   ├── beegfs.py
│   ├── local.py
│   ├── lustre.py
│   ├── nfs.py
│   └── storage.py
└── workload
    ├── cobalt.py
    ├── flux.py
    ├── kubernetes.py
    ├── moab.py
    ├── oar.py
    ├── pbs.py
    ├── slurm.py
    ├── torque.py
    └── workload.py
```

We need to automatically detect all providers as type "software" or "workload" based on their base class, `BaseProvider`.
Each provider has a probe function that will return True/False if the provider exists. The secretary will only keep instances for those that return true on startup. Each provider has what you'd expect - different tools (functions) along with metadata. The cool trick is that the base class exposes the functions for the agent like with MCP - but instead of some list I add `@secretary_tool`

## Usage

This library will be used by agents and secretaries. You can also run it locally to detect or list providers.

### Providers

```bash
$ resource-secretary providers
```
```console
╭─────────────────────────────────────────╮
│ 🦊 Resource Secretary: Provider Catalog │
╰─────────────────────────────────────────╯
                                               Available Resource Providers
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category  ┃ Name          ┃ Active ┃ Description                                                                       ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ WORKLOAD  │ COBALT        │   NO   │ Handles discovery for the Cobalt resource manager (commonly used at ALCF).        │
│ WORKLOAD  │ FLUX          │   NO   │ The Flux provider interacts with the Flux Framework using native Python bindings. │
│ WORKLOAD  │ KUBERNETES    │  YES   │ Manages interaction with Kubernetes clusters.                                     │
│ WORKLOAD  │ MOAB          │   NO   │ Handles discovery for the Moab cluster scheduler.                                 │
│ WORKLOAD  │ OAR           │   NO   │ Handles discovery for the OAR resource manager.                                   │
│ WORKLOAD  │ PBS           │   NO   │ Handles discovery and status for OpenPBS and PBS Pro.                             │
│ WORKLOAD  │ SLURM         │   NO   │ The Slurm provider manages interaction with the Slurm Workload Manager.           │
│ WORKLOAD  │ TORQUE        │   NO   │ Handles discovery for the Torque resource manager.                                │
│ SOFTWARE  │ MODULES       │   NO   │ Handles Environment Modules (Lmod or TCL).                                        │
│ SOFTWARE  │ SPACK         │   NO   │ The Spack provider handles software environment discovery and package lookups.    │
│ CONTAINER │ CHARLIECLOUD  │   NO   │ No description provided.                                                          │
│ CONTAINER │ SHIFTER       │   NO   │ No description provided.                                                          │
│ CONTAINER │ APPTAINER     │  YES   │ Provider for the Apptainer container runtime.                                     │
│ CONTAINER │ SINGULARITY   │  YES   │ Provider for the Singularity container runtime.                                   │
│ STORAGE   │ BEEGFS        │   NO   │ Handles discovery and status for BeeGFS parallel filesystems.                     │
│ STORAGE   │ LOCAL-SCRATCH │   NO   │ Identifies high-speed local filesystems (XFS, ZFS, BTRFS) used for local scratch. │
│ STORAGE   │ LUSTRE        │   NO   │ Handles discovery and status for Lustre parallel filesystems.                     │
│ STORAGE   │ NETWORK-FS    │   NO   │ Handles discovery for standard network filesystems (NFS, CIFS).                   │
│ NETWORK   │ ETHERNET      │  YES   │ Handles discovery and status for standard Ethernet interfaces.                    │
│ NETWORK   │ INFINIBAND    │   NO   │ Handles discovery and status for InfiniBand and RDMA fabrics.                     │
│ NETWORK   │ OMNI-PATH     │   NO   │ Handles discovery and status for Intel Omni-Path (OPA) fabrics.                   │
│ HARDWARE  │ AMD-GPU       │   NO   │ Handles discovery and status for AMD GPU accelerators (ROCm).                     │
│ HARDWARE  │ CPU           │  YES   │ Handles discovery of CPU architecture, core counts, and instruction sets.         │
│ HARDWARE  │ MEMORY        │  YES   │ Handles discovery of system memory (RAM).                                         │
│ HARDWARE  │ NVIDIA-GPU    │   NO   │ Handles discovery and status for NVIDIA GPU accelerators.                         │
│ PARALLEL  │ MPICH         │   NO   │ Specialized provider for MPICH implementations.                                   │
│ PARALLEL  │ OPENMPI       │   NO   │ Specialized provider for OpenMPI implementations.                                 │
│ PARALLEL  │ SPECTRUM-MPI  │   NO   │ Specialized provider for IBM Spectrum MPI.                                        │
└───────────┴───────────────┴────────┴───────────────────────────────────────────────────────────────────────────────────┘
Active = YES indicates the resource was discovered on your local system.
```

### Detect

```bash
# Run detection for all types and interfaces
$ resource-secretary detect

# Run detection for all containers
$ resource-secretary detect container

# Just detect for singularity
```
```console
╭────────────────────────────────────────────────╮
│ Resource Secretary - System Detect (Container) │
╰────────────────────────────────────────────────╯
                    Provider Manifest
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category  ┃ Provider    ┃ Metadata (Static)           ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ CONTAINER │ SINGULARITY │ {                           │
│           │             │   "runtime": "singularity", │
│           │             │   "version": "4.2.1-noble", │
│           │             │   "cache_dir": "default"    │
│           │             │ }                           │
└───────────┴─────────────┴─────────────────────────────┘

Tool Discovery (Agent Visibility)
 • singularity: list_cache
```

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](LICENSE),
[COPYRIGHT](COPYRIGHT), and
[NOTICE](NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
