# core/rag_utils.py
"""
RAG (Retrieval Augmented Generation) utilities for grounding chat responses in sources.
"""
import re
from io import BytesIO
from typing import List, Dict, Tuple
from django.db.models import Q
from .models import Source


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 50) -> str:
    """
    Extract text from PDF bytes using pdfminer.six

    Args:
        pdf_bytes: Raw PDF file bytes
        max_pages: Maximum pages to extract (to avoid huge documents)

    Returns:
        Extracted text content
    """
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        output = BytesIO()
        pdf_stream = BytesIO(pdf_bytes)

        extract_text_to_fp(
            pdf_stream,
            output,
            laparams=LAParams(),
            output_type='text',
            codec='utf-8'
        )

        text = output.getvalue().decode('utf-8')
        return text[:50000]  # Limit to 50k chars to avoid token limits
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""


def search_sources(instrument_id: str, query: str, limit: int = 5) -> List[Dict]:
    """
    Search sources for an instrument using keyword matching.

    Args:
        instrument_id: UUID of instrument
        query: User's search query
        limit: Maximum number of sources to return

    Returns:
        List of source dicts with id, title, excerpt, type
    """
    # Get all non-archived sources for this instrument
    sources = Source.objects.filter(
        instrument_id=instrument_id,
        archived=False
    ).exclude(status='rejected')

    # Extract keywords from query (simple approach)
    keywords = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]

    # Score sources based on keyword matches in title, description, category
    scored_sources = []

    for source in sources:
        score = 0
        searchable_text = f"{source.title} {source.description or ''} {source.category or ''}".lower()

        # Count keyword matches
        for keyword in keywords:
            if keyword in searchable_text:
                score += searchable_text.count(keyword)

        # Boost certain document types
        if source.category in ['manual', 'troubleshooting', 'sop']:
            score *= 1.5

        if score > 0:
            scored_sources.append({
                'source': source,
                'score': score
            })

    # Sort by score and take top results
    scored_sources.sort(key=lambda x: x['score'], reverse=True)
    top_sources = scored_sources[:limit]

    # Format results
    results = []
    for item in top_sources:
        source = item['source']

        # Create excerpt from description or title
        excerpt = source.description[:200] if source.description else source.title
        if len(source.description or '') > 200:
            excerpt += "..."

        results.append({
            'id': str(source.id),
            'title': source.title,
            'excerpt': excerpt,
            'type': source.type,
            'category': source.category,
            'score': item['score']
        })

    return results


def build_context_prompt(question: str, sources: List[Dict], instrument_context: dict = None) -> str:
    """
    Build a context-aware prompt for OpenAI with source information and instrument context.

    Args:
        question: User's question
        sources: List of relevant source dicts from search_sources()
        instrument_context: Dict with instrument info (name, vendor, description, models)

    Returns:
        Formatted prompt string
    """
    # Build instrument context
    instrument_info = ""
    if instrument_context:
        instrument_info = f"""
Instrument Information:
- Name: {instrument_context.get('name', 'Unknown')}
- Vendor: {instrument_context.get('vendor', 'Unknown')}
- Models: {', '.join(instrument_context.get('models_arr', []))}
- Description: {instrument_context.get('description', 'N/A')}
"""

    if not sources:
        return f"""You are a helpful laboratory instrument assistant providing information about specific laboratory equipment.

{instrument_info}

User question: {question}

Please provide a helpful answer about this instrument. Note: No specific documentation sources were found for this query, but you can provide general information about the instrument based on its type and common usage."""

    # Build context from sources
    context_parts = []
    for idx, source in enumerate(sources, 1):
        context_parts.append(f"""
[Source {idx}] - {source['title']} ({source['category'] or source['type']})
{source['excerpt']}
""")

    context_text = "\n".join(context_parts)

    prompt = f"""You are a helpful laboratory instrument assistant. Answer questions based on the provided documentation about this specific instrument.

{instrument_info}

Available Documentation:
{context_text}

User Question: {question}

Instructions:
1. Answer the question using information from the sources above
2. Reference the specific instrument by name when relevant
3. When referencing information from documentation, cite the source using [Source N] format
4. If the sources don't contain relevant information, say so clearly
5. Be concise but thorough
6. You can use markdown formatting for better readability (lists, bold, code blocks, etc.)

Answer:"""

    return prompt


def parse_citations_from_response(response_text: str, sources: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Parse citation markers from OpenAI response and link to actual sources.

    Args:
        response_text: OpenAI's response text containing [Source N] markers
        sources: List of source dicts used in the prompt

    Returns:
        Tuple of (response_text, list of citation dicts)
    """
    citations = []
    citation_pattern = r'\[Source (\d+)\]'

    # Find all citation markers
    matches = re.finditer(citation_pattern, response_text)

    for match in matches:
        source_num = int(match.group(1))

        # Convert to 0-based index
        source_idx = source_num - 1

        if 0 <= source_idx < len(sources):
            source = sources[source_idx]

            # Create citation entry
            citations.append({
                'source_id': source['id'],
                'source_title': source['title'],
                'source_type': source['type'],
                'citation_text': match.group(0),
                'score': 0.9  # High confidence for direct citations
            })

    # Remove duplicates
    seen = set()
    unique_citations = []
    for cite in citations:
        key = cite['source_id']
        if key not in seen:
            seen.add(key)
            unique_citations.append(cite)

    return response_text, unique_citations


def get_or_extract_source_text(source: Source) -> str:
    """
    Get text content from a source, extracting if needed.
    For now, returns description/title. In future, can extract from storage_uri.

    Args:
        source: Source model instance

    Returns:
        Text content
    """
    # For MVP, use description + title
    # TODO: Implement actual file extraction from MinIO storage_uri
    text_parts = [source.title]

    if source.description:
        text_parts.append(source.description)

    if source.version:
        text_parts.append(f"Version: {source.version}")

    if source.model_tags:
        text_parts.append(f"Models: {', '.join(source.model_tags)}")

    return "\n".join(text_parts)
