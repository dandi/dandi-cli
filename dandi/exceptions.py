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


class LockingError(RuntimeError):
    """Failed to lock or unlock a resource"""

    pass


class CliVersionError(RuntimeError):
    """ Base class for `CliVersionTooOldError` and `BadCliVersionError` """

    def __init__(self, our_version, minversion, bad_versions):
        self.our_version = our_version
        self.minversion = minversion
        self.bad_versions = bad_versions

    def server_requirements(self):
        s = f"Server requires at least version {self.minversion}"
        if self.bad_versions:
            s += f" (but not {', '.join(map(str, self.bad_versions))})"
        return s


class CliVersionTooOldError(CliVersionError):
    def __str__(self):
        return (
            f"Client version {self.our_version} is too old!  "
            + self.server_requirements()
        )


class BadCliVersionError(CliVersionError):
    def __str__(self):
        return (
            f"Client version {self.our_version} is rejected by server!  "
            + self.server_requirements()
        )
