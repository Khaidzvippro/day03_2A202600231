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
    
    # Clean the text first
    text = clean_text(text)
    
    # Try to find explicit "Abstract" section
    abstract_match = re.search(
        r'(?:abstract|summary|overview)\s*[:\-]?\s*(.+?)(?=\n\n|\nintroduction|\nbackground|\nmethod|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Clean the extracted abstract
        abstract = clean_text(abstract)
        return abstract
    
    # If no explicit abstract, extract first paragraph
    paragraphs = text.split('\n\n')
    if paragraphs:
        first_para = clean_text(paragraphs[0])
        # Limit to max_sentences
        sentences = re.split(r'(?<=[.!?])\s+', first_para)
        limited_abstract = ' '.join(sentences[:max_sentences])
        return limited_abstract
    
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
