"""
Tool registry for the ReAct Agent.
Import ALL_TOOLS to get the full list of available tools.
"""

from src.tools.search import SEARCH_ARXIV_TOOL, GET_PAPER_ABSTRACT_TOOL
from src.tools.formatter import ALPHA_FORMATTER_TOOL

ALL_TOOLS = [
    SEARCH_ARXIV_TOOL,
    GET_PAPER_ABSTRACT_TOOL,
    ALPHA_FORMATTER_TOOL,
]
