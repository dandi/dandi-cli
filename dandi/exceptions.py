class OrganizeImpossibleError(ValueError):
    """Exception to be raised if given current list of files it is impossible

    E.g. if metadata is not sufficient or conflicting
    """

    pass


class UnknownURLError(ValueError):
    """Given url is not known to correspond to DANDI archive schema(s)"""

    pass


class NotFoundError(RuntimeError):
    """Online resource which we tried to connect to is not found"""

    pass


class FailedToConnectError(RuntimeError):
    """Failed to connect to online resource"""

    pass
