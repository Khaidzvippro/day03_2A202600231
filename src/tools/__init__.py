"""
Tool registry for the ReAct Agent.
Import ALL_TOOLS to get the full list of available tools.
"""

from src.tools.search import SEARCH_ARXIV_TOOL, GET_PAPER_ABSTRACT_TOOL
from src.tools.formatter import ALPHA_FORMATTER_TOOL
from src.tools.reader import EXTRACT_ABSTRACT_TOOL, EXTRACT_METADATA_TOOL

ALL_TOOLS = [
    SEARCH_ARXIV_TOOL,         # search_arxiv(query=...)
    GET_PAPER_ABSTRACT_TOOL,   # get_paper_abstract(paper_id=...)
    EXTRACT_ABSTRACT_TOOL,     # extract_abstract(text=...)
    EXTRACT_METADATA_TOOL,     # extract_metadata(text=...)
    ALPHA_FORMATTER_TOOL,      # alpha_formatter(text=...)
]
