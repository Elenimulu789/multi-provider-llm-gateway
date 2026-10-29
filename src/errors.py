"""Public errors contain only fixed, actionable messages, never SDK payloads."""
class GatewayProviderError(Exception):
    code = "provider_error"
    def __init__(self, provider: str = "gateway"):
        self.provider = provider
        super().__init__(f"{provider}: request failed. Check provider availability and account access.")

class AuthenticationError(GatewayProviderError):
    code = "authentication"
    def __init__(self, provider="gateway"):
        self.provider = provider
        Exception.__init__(self, f"{provider}: missing, malformed, revoked or unauthorized API key. Check server secrets or .env.")

class RateLimitExceededError(GatewayProviderError):
    code = "rate_limit_or_quota"
    def __init__(self, provider="gateway"):
        self.provider = provider
        Exception.__init__(self, f"{provider}: rate limit or account quota reached. Check credits and limits before retrying.")

class GatewayConnectionError(GatewayProviderError):
    code = "connection"
    def __init__(self, provider="gateway"):
        self.provider = provider
        Exception.__init__(self, f"{provider}: connection failed or request timed out. Check your network and retry manually.")

class InvalidRequestError(GatewayProviderError):
    code = "invalid_request"
    def __init__(self, provider="gateway"):
        self.provider = provider
        Exception.__init__(self, f"{provider}: request or model unavailable. Use a listed model and verify account access.")

class IncompleteStreamError(GatewayProviderError):
    code = "incomplete_stream"
    def __init__(self, provider="gateway"):
        self.provider = provider
        Exception.__init__(self, f"{provider}: stream ended before the completion marker. Partial text and estimates are not a completed response.")
