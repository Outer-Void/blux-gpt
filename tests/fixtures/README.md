# Provider fixtures

Hand-written from each provider's public API reference, not captured traffic: they contain no real ids,
keys or user data. `conftest.FakeProvider` serves them over local HTTP so the real transport, streaming and
normalization code runs offline. Tests that talk to real providers are separate (`test_real_providers.py`,
marker `real`) and say so in their output.
