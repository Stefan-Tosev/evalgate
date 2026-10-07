"""evalgate — a regression gate for non-deterministic model output.

The premise: an LLM feature cannot be tested with one sample and a boolean.
Run each case N times, report a pass *rate*, and gate CI on movement against a
committed baseline rather than on an absolute score.
"""

__version__ = "0.1.0"
