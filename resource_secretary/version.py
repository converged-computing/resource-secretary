__version__ = "0.0.1"
AUTHOR = "Vanessa Sochat"
AUTHOR_EMAIL = "vsoch@users.noreply.github.com"
NAME = "resource-secretary"
PACKAGE_URL = "https://github.com/converged-computing/resource-secretary"
KEYWORDS = "workload managers, package managers, and other resource discovery"
DESCRIPTION = (
    "Discover providers for resources (software, workload managers) for agentic science and beyond!"
)
LICENSE = "LICENSE"


################################################################################
# TODO vsoch: refactor this to use newer pyproject stuff.

INSTALL_REQUIRES = (
    ("rich", {"min_version": None}),
    ("psutil", {"min_version": None}),
)

TESTS_REQUIRES = (("pytest", {"min_version": "4.6.2"}),)

INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
