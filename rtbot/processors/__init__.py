from .autosort import AutoSort
from .uia import MergeUiATickets
from .autoreply import ResolveAutoReplies
from .ccc import ResolveCccReceipts
from .take_away import TakeAway

processors = [
    TakeAway,
    ResolveAutoReplies,
    ResolveCccReceipts,
    MergeUiATickets,
    AutoSort,
]


def get_processors(*args, **kwargs):
    return [cls(*args, **kwargs) for cls in processors]
