from typing import ClassVar

from avrogen.dict_wrapper import DictWrapper


class _BaseMLEntity():
    """Base class for ML Entity
    """

    def __init__(self):
        if type(self) is _BaseMLEntity:
            raise TypeError(
                "cannot instantiate _BaseMLEntity directly"
            )
