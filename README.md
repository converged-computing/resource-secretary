# resource secretary

> Discover providers for resources (software, workload managers) for agentic science and beyond!

![img/resource-secretary.png](img/resource-secretary.png)

[![PyPI version](https://badge.fury.io/py/resource-secretary.svg)](https://badge.fury.io/py/resource-secretary)


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

```
resource_secretary/providers/
├── container
│   ├── charliecloud.py
│   ├── shifter.py
│   ├── oci.py          # includes docker and podman
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
│   ├── interconnect.py
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
    ├── flux.py
    ├── kubernetes.py
    └── slurm.py
```

We need to automatically detect all providers as type "software" or "workload" based on their base class, `BaseProvider`.
Each provider has a probe function that will return True/False if the provider exists. The secretary will only keep instances for those that return true on startup. Each provider has what you'd expect - different tools (functions) along with metadata. The cool trick is that the base class exposes the functions for the agent like with MCP - but instead of some list I add `@secretary_tool`

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](LICENSE),
[COPYRIGHT](COPYRIGHT), and
[NOTICE](NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
