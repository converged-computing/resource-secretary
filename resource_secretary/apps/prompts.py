import itertools

import resource_secretary.utils as utils


class AppPromptGenerator:
    """
    Generate combinatorial prompt matrices.
    Sandwich: [Manager] [Manager Flags] [Resources] [Binary] [App Config] [App Flags]
    """

    @staticmethod
    def generate(
        templates: dict,
        truth_template: str,
        params: dict,
        flatten: bool = False,
        filters: str = None,
        count: int = None,
    ):
        matrix = [] if flatten else {}

        # Get different components and add app
        if "app" not in params:
            params["app"] = templates.application

        core_components = ["manager", "resources", "app_config"]
        modifiers = [k for k in templates.matrix.keys() if k.startswith("modifier_")]
        all_components = core_components + modifiers

        # Extract variants for the product
        variant_levels = []
        for c in all_components:
            item = templates.matrix[c]["variants"]
            variant_levels.append(list(item.keys()))

        # Combinatorial loop fwoop
        for combo in itertools.product(*variant_levels):
            key = "|".join(
                [
                    f"{all_components[i].replace('modifier_', '')}:{combo[i]}"
                    for i in range(len(combo))
                ]
            )

            # Filter early on
            if filters and filters not in key:
                continue
            manager_flags, app_flags, prompt_parts = [], [], []
            is_discovery = False

            for i, component_name in enumerate(all_components):
                variant_style = combo[i]
                component_data = templates.matrix[component_name]

                # Get the prompt text for this style
                # variants -> exact -> prompt
                prompt_text = component_data["variants"][variant_style]
                prompt_parts.append(prompt_text.format(**params))
                if variant_style == "discovery":
                    is_discovery = True

                # Handle Command Flags (only for modifiers)
                if component_name.startswith("modifier_"):
                    metadata = component_data.get("metadata", {})
                    flag = metadata.get("flag", "")

                    if metadata.get("type") == "manager":
                        manager_flags.append(flag)
                    else:
                        app_flags.append(flag)

            # Assemble outputs
            full_prompt = " ".join([p for p in prompt_parts if p]).strip() + "."
            full_command = truth_template.format(
                manager_mods=" ".join(manager_flags), app_mods=" ".join(app_flags), **params
            )

            # This is the case when the manager is going to say "find everything in this context"
            if is_discovery:
                if "nodes" in params:
                    full_command = full_command.replace(f"-N{params['nodes']}", "-N <nodes>")
                if "tasks" in params:
                    full_command = full_command.replace(f"-n {params['tasks']}", "-n <tasks>")

            prompt = " ".join(full_prompt.split())

            # Warning to all - "Capitalize" will make the rest of the sentence lowercase...
            first_letter = prompt[0].capitalize()
            prompt = first_letter + prompt[1:]
            entry = {
                "command": " ".join(full_command.split()),
                "prompt": prompt,
                "prompt_style": key,
                "ground_truth_params": params,
            }
            if flatten:
                matrix.append(entry)
            else:
                matrix[key] = entry

        # Return and make sure to shuffle
        matrix = utils.shuffle(matrix)
        if count and len(matrix) > count:
            matrix = utils.clip(matrix, count)
        return matrix
