class BridgeError(Exception):
    """Base for all bridge-domain errors. Carries an Impulse response code."""

    code: int = 99
    message: str = "Internal bridge error"

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class CollectionNotFound(BridgeError):
    code = 1
    message = "Collection not found"


class SourceNotFound(BridgeError):
    """An archive source id that is not configured (web app API)."""

    code = 1
    message = "Source not found"


class AssetNotFound(BridgeError):
    code = 2
    message = "Asset not found"


class UpstreamUnavailable(BridgeError):
    code = 10
    message = "Upstream source unavailable"


class UpstreamRateLimited(BridgeError):
    code = 11
    message = "Upstream rate limit reached"


class UpstreamMalformed(BridgeError):
    code = 12
    message = "Upstream returned malformed data"


class UpstreamNotFound(UpstreamMalformed):
    """The upstream answered 404 for a specific resource. Same Impulse code as
    UpstreamMalformed unless a caller knows better — the REST adapter's detail
    lookup turns it into AssetNotFound (code 2)."""


class ConfigError(BridgeError):
    code = 20
    message = "Bridge configuration error"
