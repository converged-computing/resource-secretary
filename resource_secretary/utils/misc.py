import random


def shuffle(item):
    """
    Randomly shuffle a list or dict.
    """
    if isinstance(item, list):
        random.shuffle(item)
        return item
    elif isinstance(item, dict):
        items = list(item.items())
        random.shuffle(items)
        return dict(items)
    raise ValueError(f"Cannot shuffle {type(item)}")


def clip(items, count):
    if len(items) <= count:
        return items
    if isinstance(items, (list, str)):
        return items[:count]
    elif isinstance(items, dict):
        items = list(items.items())[:count]
        return dict(items)
    raise ValueError(f"Cannot shuffle {type(item)}")
