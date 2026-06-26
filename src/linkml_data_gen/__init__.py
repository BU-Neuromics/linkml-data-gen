"""linkml-data-gen: stochastic, schema-valid test data for any LinkML schema."""

from .config import GenerationConfig
from .generator import DataGenerator

__all__ = ["DataGenerator", "GenerationConfig", "__version__"]
__version__ = "0.1.0"
