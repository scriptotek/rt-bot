from .autosort import AutoSort
from .uia import MergeUiATickets
from .autoreply import ResolveAutoReplies


def get_processors(*args, **kwargs):
    return [
        ResolveAutoReplies(*args, **kwargs),
        MergeUiATickets(*args, **kwargs),
        AutoSort(*args, **kwargs),
    ]
