"""Reproducible property-test generation in the locked test environment."""
from hypothesis import settings

settings.register_profile('ahas', derandomize=True, database=None, deadline=None)
settings.load_profile('ahas')
