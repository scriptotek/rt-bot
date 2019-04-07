from .autosort import AutoSort
from .uia import MergeUiATickets


def get_processors(*args, **kwargs):
    return [
        MergeUiATickets(*args, **kwargs),
        AutoSort(*args, **kwargs),
    ]
