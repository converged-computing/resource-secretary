from ..provider import BaseProvider


class MockBaseProvider(BaseProvider):
    """
    Base for all mock providers to ensure they accept a config on init.
    """

    def __init__(self, config):
        super().__init__()
        self.config = config

    def generate(self, key: str, mode: str = "scale", volatility: float = 0.1) -> int:
        """
        A mock provider can generate a state based on an archetype, a type (scale or density)
        and volatility. E.g.,:
        - key is the resource to generate, like nodes, partitions, software packages
        - mode is what mindset (mode) to use. E.g., scale is size, density is "how much stuff"
            Note from V: I am thinking of scale as size, and density as information. The
            LLM could fail for either. E.g., high node count (bigness) vs. software (unique).
        - volatility is how much we allow drift from the global config for the archetype.
        The last is to say "I am very different."
        """
        # Range from the worker's archetype, if defined
        min_v, max_v = self.config.archetype.ranges.get(key, (0, 0))

        # Global target (like an anchor) based on the type
        anchor = self.config.targets.get(mode) or self.config.get_default_target()

        # Provider-specific RNG (should be like a sense of stability)
        rng = self.config.get_rng(self.name)

        # Allow for drift from what the archetype allows
        # aka "I am STILL a special snowflake"
        # High volatility = Provider ignores the system anchor.
        # Low volatility = Provider follows the system anchor strictly.
        factor = rng.gauss(anchor, volatility)
        factor = max(0.01, min(1.0, factor))
        return int(min_v + (factor * (max_v - min_v)))
