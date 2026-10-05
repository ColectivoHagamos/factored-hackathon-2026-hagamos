"""The controllers of the HTTP API: thin routers that check who calls, hand the request to one use case and return
its body. They hold no business rule and reach no adapter."""

API_PREFIX = "/v1"
