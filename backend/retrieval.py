"""Local passage retrieval. The active engine is always disclosed."""
import os
import re
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@lru_cache(maxsize=1)
def model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'))
def rank(query, entries, limit=5):
    if not entries:
        return [], 'TF-IDF cosine similarity'
    texts = [entry['passage'] for entry in entries]
    if os.getenv('EMBEDDING_BACKEND') == 'sentence-transformers':
        import faiss
        encoder = model()
        vectors = np.asarray(encoder.encode(texts, normalize_embeddings=True), dtype='float32')
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        scores, indices = index.search(np.asarray(encoder.encode([query], normalize_embeddings=True), dtype='float32'), min(limit, len(entries)))
        return [dict(entries[int(i)], score=round(float(s), 4)) for i, s in zip(indices[0], scores[0]) if s > .05], 'Sentence Transformers / FAISS'
    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform(texts + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        return [], 'TF-IDF cosine similarity'
    order = np.argsort(-scores)[:limit]
    return [dict(entries[i], score=round(float(scores[i]), 4)) for i in order if scores[i] > .025], 'TF-IDF cosine similarity'
def passages(documents):
    entries = []
    for doc in documents:
        for start in range(0, len(doc.content), 900):
            entries.append({'document_id': doc.id, 'title': doc.title, 'source': doc.source, 'published_at': doc.published_at, 'passage': doc.content[start:start+1100]})
    return entries
def summarize(hits):
    if not hits:
        return 'No supporting passages were found. Add relevant documents or refine the query.'
    sentences = []
    for hit in hits[:3]:
        sentence = re.split(r'(?<=[.!?])\s+', hit['passage'])[0]
        sentences.append(f'[{hit["document_id"]}] {sentence}')
    return '\n\n'.join(sentences)
