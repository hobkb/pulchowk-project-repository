#!/usr/bin/env python
"""
Diagnostic script to verify the Chroma vector store is populated correctly.

Run from the RAG project root:
    python verify_chromadb.py
    python verify_chromadb.py "your test query here"
"""

import sys
from src.ingestion.vector_store import StatefulVectorPipeline

def main():
    
    vp = StatefulVectorPipeline()
    collection = vp.collection
    collection.count()
    item = collection.get(limit=1, include=["embeddings", "documents"])
    print(item)
    total = collection.count()
    print(f"Vector DB path      : {vp.db_path}")
    print(f"Collection name     : {collection.name}")
    print(f"Total chunks stored : {total}")
    print("-" * 60)

    if total == 0:
        print("Collection is EMPTY. Run `python run_ingestion.py` first.")
        return

    # 1. Sample a few records to eyeball structure
    sample = collection.get(limit=5, include=["metadatas", "documents"])
    print("Sample records:\n")
    for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
        print(f"  [{i}] file={meta.get('source_file')} | page={meta.get('page_number')} "
              f"| chapter={meta.get('chapter')} | section={meta.get('section_number')}")
        print(f"      text: {doc[:100]}...")
    print("-" * 60)

    # 2. List distinct source files actually indexed
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    files = sorted(set(m.get("source_file") for m in all_meta))
    print(f"Distinct files indexed ({len(files)}):")
    for f in files:
        count = sum(1 for m in all_meta if m.get("source_file") == f)
        print(f"  - {f}: {count} chunks")
    print("-" * 60)

    # 3. Run an actual semantic query to prove embeddings work end-to-end
    query = sys.argv[1] if len(sys.argv) > 1 else "system architecture and methodology"
    print(f"Test query: '{query}'\n")
    results = collection.query(query_texts=[query], n_results=5, include=["documents", "metadatas", "distances"])

    if not results["ids"][0]:
        print("Query returned no results.")
        return

    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i]
        doc = results["documents"][0][i]
        print(f"  #{i+1} dist={dist:.4f} | file={meta.get('source_file')} | section={meta.get('section_title')}")
        print(f"      {doc[:100]}...")

    print("\nIf the top results are semantically relevant to your query, embeddings are working correctly.")


if __name__ == "__main__":
   
    main()