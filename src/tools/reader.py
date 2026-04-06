import re
import unicodedata
from typing import Optional, Dict, Any

def clean_text(text: str) -> str:
    """
    Clean text by removing or normalizing strange characters.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text with normalized unicode and removed control characters
    """
    if not text:
        return ""
    
    # Normalize unicode characters (NFC = composed form, better for display)
    text = unicodedata.normalize('NFC', text)
    
    # Remove control characters and other problematic unicode
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_abstract(text: str, max_sentences: int = 5) -> Optional[str]:
    """
    Extract abstract from text. Looks for an explicit Abstract section or 
    extracts the first paragraph if no abstract is found.
    
    Args:
        text: Full text to extract abstract from
        max_sentences: Maximum number of sentences to include if no explicit abstract
        
    Returns:
        Extracted abstract or None if text is empty
    """
    if not text:
        return None

    # Work on original text so newlines are preserved for structural detection.
    # clean_text collapses all whitespace to a single space, which would destroy
    # the \n\n paragraph boundaries the regex relies on.

    # Try to find explicit "Abstract" section
    abstract_match = re.search(
        r'(?:abstract|summary|overview)\s*[:\-]?\s*(.+?)(?=\n\n|\nintroduction|\nbackground|\nmethod|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )

    if abstract_match:
        return clean_text(abstract_match.group(1))

    # If no explicit abstract, extract first non-empty paragraph
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    if paragraphs:
        first_para = clean_text(paragraphs[0])
        sentences = re.split(r'(?<=[.!?])\s+', first_para)
        return ' '.join(sentences[:max_sentences])

    return None


def extract_metadata(text: str) -> Dict[str, Any]:
    """
    Extract metadata from text (title, authors, abstract, etc.)
    
    Args:
        text: Input text to extract metadata from
        
    Returns:
        Dictionary with extracted metadata
    """
    if not text:
        return {}
    
    metadata = {
        'abstract': extract_abstract(text),
        'cleaned_text': clean_text(text),
        'length': len(clean_text(text)),
        'word_count': len(clean_text(text).split()),
    }
    
    # Try to extract title (usually first line or after common patterns)
    title_match = re.match(r'^(.+?)(?:\n|$)', text)
    if title_match:
        title = clean_text(title_match.group(1))
        if len(title) > 10 and len(title) < 300:  # Reasonable title length
            metadata['title'] = title

    return metadata


# ── Tool Registry Entries ─────────────────────────────────────────────────────

EXTRACT_ABSTRACT_TOOL = {
    "name": "extract_abstract",
    "description": (
        "Extract and clean the abstract section from raw paper text. "
        "Parameter: text (string) — raw paper content. "
        "Call format: extract_abstract(text=\"raw paper content here\"). "
        "Returns the cleaned abstract string, or None if not found."
    ),
    "function": extract_abstract,
}

EXTRACT_METADATA_TOOL = {
    "name": "extract_metadata",
    "description": (
        "Extract structured metadata (title, abstract, word count) from raw paper text. "
        "Parameter: text (string) — raw paper content. "
        "Call format: extract_metadata(text=\"raw paper content here\"). "
        "Returns a dict with keys: abstract, cleaned_text, length, word_count, title."
    ),
    "function": extract_metadata,
}
