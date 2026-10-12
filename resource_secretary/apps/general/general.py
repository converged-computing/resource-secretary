from resource_secretary.apps.app import BaseApplication
from resource_secretary.apps.prompts import AppPromptGenerator


class GeneralApplication(BaseApplication):
    """
    General application, functions to support dispatch or probing.
    """

    @property
    def name(self):
        return "general"
