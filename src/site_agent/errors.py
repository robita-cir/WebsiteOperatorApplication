"""Errors that are shown to the operator as one short line, not as a traceback."""


class SiteAgentError(Exception):
    """A problem the operator can fix: a missing file, bad input, or a change that was refused."""
