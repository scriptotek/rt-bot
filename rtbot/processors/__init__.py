from .autosort import AutoSort
from .uia import MergeUiATickets
from .autoreply import ResolveAutoReplies
from .ccc import ResolveCccReceipts


def get_processors(*args, **kwargs):
    return [
        ResolveAutoReplies(*args, **kwargs),
        ResolveCccReceipts(*args, **kwargs),
        MergeUiATickets(*args, **kwargs),
        AutoSort(*args, **kwargs),
    ]
