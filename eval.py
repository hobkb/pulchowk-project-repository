import os
import json
import re

# =====================================================================
# 1. THE INGESTION CHUNKER
# =====================================================================
class ProjectLevelChunker:
    # Stopwords to combat semantic dilution and eliminate academic noise
    STOPWORDS = {
        "the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "with", "by", "as", "is", "are", 
        "was", "were", "be", "been", "being", "this", "that", "these", "those", "it", "its", "from", 
        "at", "into", "which", "will", "can", "also", "our", "we", "such", "than", "but", "about",
        "project", "system", "report", "study", "research", "paper", "thesis", "chapter", "figure", 
        "table", "results", "analysis", "abstract", "introduction", "background", "conclusion", 
        "proposed", "proposal", "work", "document", "overview", "summary", "using", "used", "based"
    }

    _DOMAIN_RULES = {
        "Biomedical AI & Signal Processing": {"ppg", "ecg", "eeg", "cardiovascular", "heart", "pulse", "sensor"},
        "Computer Vision & Image Processing": {"image", "video", "opencv", "face", "yolo", "detection", "cnn", "camera", "surveillance", "optical", "flow"},
        "Natural Language Processing": {"text", "language", "sentence", "bert", "transformer", "nlp", "sbert", "similarity"},
        "Web & Mobile Applications": {"react", "django", "frontend", "backend", "api", "database", "postgresql", "rest"},
        "Hardware & IoT Systems": {"arduino", "esp32", "sensor", "microcontroller", "iot", "hardware"}
    }

    @staticmethod
    def clean_text(text: str) -> str:
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)  # fix PDF hyphens
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def extract_technical_entities(cls, text: str, title: str) -> list:
        words = re.findall(r"\b[A-Za-z0-9_-]{3,}\b", text.lower())
        title_words = set(re.findall(r"\b[A-Za-z0-9_-]{3,}\b", title.lower()))
        exclude = cls.STOPWORDS.union(title_words)
        
        filtered = [w for w in words if w not in exclude and not w.isdigit()]
        # Return top unique keywords in order of appearance
        seen = set()
        return [w for w in filtered if not (w in seen or seen.add(w))][:15]

    @classmethod
    def infer_domain(cls, text: str) -> str:
        text_words = set(re.findall(r"\b[A-Za-z0-9_-]{3,}\b", text.lower()))
        detected = [domain for domain, terms in cls._DOMAIN_RULES.items() if not terms.isdisjoint(text_words)]
        return ", ".join(detected) or "Software Engineering"

    @staticmethod
    def parse_sections(chunks: list) -> dict:
        """Helper to classify and group abstract vs other chunks."""
        abstract_parts = []
        other_parts = []
        
        for chunk in chunks:
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            
            page_type = meta.get("page_type", "").lower()
            sec_title = meta.get("section_title", "").lower()
            
            if "abstract" in page_type or "abstract" in sec_title:
                abstract_parts.append(text)
            else:
                other_parts.append(text)
                
        return {
            "abstract": " ".join(abstract_parts),
            "content": " ".join(other_parts)
        }

    @classmethod
    def build_weighted_payload(cls, title: str, chunks: list) -> dict:
        sections = cls.parse_sections(chunks)
        clean_abstract = cls.clean_text(sections["abstract"])
        clean_content = cls.clean_text(sections["content"])
        
        raw_pool = f"{title} {clean_abstract} {clean_content}"
        keywords = cls.extract_technical_entities(raw_pool, title)
        domain = cls.infer_domain(raw_pool)

        # Truncate content to balance the weights:
        # Tech: ~40% (Title + Keywords duplicated for attention)
        # Domain: ~30% (Categorical identifiers repeated)
        # Methodology: ~20% (First 25 words of non-abstract content)
        # Summary: ~10% (First 12 words of Abstract)
        
        tech_words = keywords[:8]
        duplicated_tech = ", ".join(tech_words + tech_words[:3])
        tech_section = f"TECHNICAL IDENTITY: {title}. STACK: {duplicated_tech}."

        domain_tags = [d.strip() for d in domain.split(",") if d.strip()]
        domain_section = f"DOMAIN CATEGORIES: {', '.join(domain_tags * 2)}."

        method_words = clean_content.split()[:25]
        method_section = f"METHODOLOGY: {' '.join(method_words)}."

        summary_words = clean_abstract.split()[:12]
        summary_section = f"SUMMARY: {' '.join(summary_words)}."

        payload = f"{tech_section}\n{domain_section}\n{method_section}\n{summary_section}"
        
        return {
            "domain": domain,
            "keywords": keywords,
            "embedding_text": payload
        }

# =====================================================================
# 2. THE EVALUATION RUNNER
# =====================================================================
def estimate_tokens(text: str) -> int:
    words = re.findall(r'\b\w+\b', text)
    return int(len(words) * 1.3)

def load_payloads_from_folder(folder_path="extracted/payloads"):
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Directory '{folder_path}' not found! Are you running this from your RAG root?")
    
    projects = []
    files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    
    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Default Title and Chunk parsing
                title = ""
                chunks = []
                
                if isinstance(data, list):
                    chunks = data
                    # Grab project_title from hierarchy of the first chunk if it exists
                    if len(data) > 0 and isinstance(data[0], dict):
                        title = data[0].get("hierarchy", {}).get("project_title")
                    
                    # Fallback to filename if hierarchy not present
                    if not title:
                        title = file_name.replace("processed_", "").replace(".json", "").replace("_", " ").strip()
                elif isinstance(data, dict):
                    title = data.get("title") or data.get("project_name") or file_name.replace("processed_", "").replace(".json", "")
                    chunks = data.get("chunks") or data.get("pages") or []

                projects.append({
                    "title": title, 
                    "chunks": chunks, 
                    "file_name": file_name
                })
        except Exception as e:
            print(f"❌ Failed to parse {file_name}: {e}")
            
    return projects

def run_ingestion_audit():
    payload_folder = "extracted/payloads"
    try:
        raw_projects = load_payloads_from_folder(payload_folder)
    except FileNotFoundError as e:
        print(e)
        return

    if not raw_projects:
        print("No files loaded.")
        return

    print("\n" + "="*60)
    print("      REAL DATA INGESTION & SEMANTIC AUDIT REPORT      ")
    print("="*60 + "\n")

    token_violations = 0

    for idx, p in enumerate(raw_projects, 1):
        # 1. Grab raw text dynamically based on 'content_body' schema
        raw_text_list = []
        normalized_chunks = []
        
        for c in p["chunks"]:
            if isinstance(c, dict):
                # Pull the actual text from "content_body"
                text_val = c.get("content_body") or c.get("text") or ""
                
                # Reconstruct metadata for our Chunker parser
                meta_val = {
                    "page_type": c.get("page_type") or "",
                    "section_title": c.get("hierarchy", {}).get("section_title") or ""
                }
                
                raw_text_list.append(str(text_val))
                normalized_chunks.append({"text": text_val, "metadata": meta_val})
            else:
                raw_text_list.append(str(c))
                normalized_chunks.append({"text": str(c), "metadata": {}})
                
        raw_text = " ".join(raw_text_list).strip()
        raw_word_count = len(raw_text.split())

        # 2. Build payload with weighted features
        payload_data = ProjectLevelChunker.build_weighted_payload(p["title"], normalized_chunks)
        embedding_payload = payload_data["embedding_text"]
        
        processed_word_count = len(embedding_payload.split())
        estimated_token_count = estimate_tokens(embedding_payload)

        budget_status = "PASS"
        if estimated_token_count > 256:
            budget_status = "!! FAIL !!"
            token_violations += 1

        print(f"File: {p['file_name']}")
        print(f"  Project: {p['title'][:45]}...")
        print(f"  ├─ Extracted Domain : {payload_data['domain']}")
        print(f"  ├─ Extracted Tech   : {', '.join(payload_data['keywords'][:5])}")
        print(f"  ├─ Raw Words        : {raw_word_count}")
        print(f"  ├─ Embedded Words   : {processed_word_count}")
        print(f"  ├─ Est. Token Count : {estimated_token_count} / 256 ({budget_status})")
        print(f"  └─ Token Headroom   : {256 - estimated_token_count} remaining\n")

    print("="*60)
    print(f"Total Files Audited     : {len(raw_projects)}")
    print(f"Token Budget Violations : {token_violations} / {len(raw_projects)}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_ingestion_audit()