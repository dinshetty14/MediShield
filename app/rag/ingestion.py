"""Policy PDF ingestion using Docling."""

from pathlib import Path

from docling.document_converter import DocumentConverter

from app.config import get_settings


def ingest_policy_pdf(pdf_path: str | Path) -> list[dict]:
    """Ingest a policy PDF and return chunks.

    Args:
        pdf_path: Path to the policy PDF file

    Returns:
        List of document chunks with text and metadata
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Policy PDF not found: {pdf_path}")

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))

    chunks = []
    doc = result.document

    # Extract text from document
    full_text = doc.export_to_markdown()

    # Split into semantic chunks by sections
    sections = _split_into_sections(full_text)

    for i, section in enumerate(sections):
        if section["text"].strip():
            chunks.append({
                "id": f"{pdf_path.stem}_chunk_{i}",
                "text": section["text"],
                "metadata": {
                    "source": str(pdf_path),
                    "section": section.get("heading", f"Section {i}"),
                    "chunk_index": i,
                    "policy_name": pdf_path.stem,
                },
            })

    return chunks


def _split_into_sections(markdown_text: str) -> list[dict]:
    """Split markdown text into sections based on headings."""
    import re

    sections = []
    current_section = {"heading": "Introduction", "text": ""}

    lines = markdown_text.split("\n")

    for line in lines:
        # Check for markdown headings
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            # Save current section if it has content
            if current_section["text"].strip():
                sections.append(current_section)

            # Start new section
            current_section = {
                "heading": heading_match.group(2).strip(),
                "text": "",
            }
        else:
            current_section["text"] += line + "\n"

    # Add final section
    if current_section["text"].strip():
        sections.append(current_section)

    # If no sections found, return entire text as one chunk
    if not sections:
        sections = [{"heading": "Full Document", "text": markdown_text}]

    # Further split large sections
    max_chunk_size = 1500
    final_chunks = []

    for section in sections:
        text = section["text"]
        if len(text) > max_chunk_size:
            # Split by paragraphs
            paragraphs = text.split("\n\n")
            current_chunk = ""

            for para in paragraphs:
                if len(current_chunk) + len(para) > max_chunk_size:
                    if current_chunk:
                        final_chunks.append({
                            "heading": section["heading"],
                            "text": current_chunk.strip(),
                        })
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para

            if current_chunk.strip():
                final_chunks.append({
                    "heading": section["heading"],
                    "text": current_chunk.strip(),
                })
        else:
            final_chunks.append(section)

    return final_chunks


def ingest_all_policies(policies_dir: str | Path | None = None) -> list[dict]:
    """Ingest all PDF files from the policies directory.

    Args:
        policies_dir: Optional path to policies directory

    Returns:
        List of all chunks from all policies
    """
    settings = get_settings()
    policies_dir = Path(policies_dir) if policies_dir else settings.policies_dir

    if not policies_dir.exists():
        policies_dir.mkdir(parents=True, exist_ok=True)
        return []

    all_chunks = []
    for pdf_file in policies_dir.glob("*.pdf"):
        try:
            chunks = ingest_policy_pdf(pdf_file)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Failed to ingest {pdf_file}: {e}")

    return all_chunks
