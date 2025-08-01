# src/search/semantic_search.py
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import streamlit as st
from sklearn.metrics.pairwise import cosine_similarity

class SemanticSearchEngine:
    """Handles semantic search over constructs and measures"""
    
    def __init__(self, embedding_path: Path):
        self.embedding_path = embedding_path
        self.model = self._load_model()
        self.embeddings = None
        self.index_to_item = None
    
    @st.cache_resource
    def _load_model(_self) -> SentenceTransformer:
        """Load the sentence transformer model"""
        return SentenceTransformer('all-MiniLM-L6-v2')
    
    def build_embeddings(self, items: List[Dict[str, str]]):
        """Build embeddings for constructs/measures"""
        texts = []
        self.index_to_item = {}
        
        for idx, item in enumerate(items):
            # Combine label and description for richer embeddings
            text = item.get('label', '')
            if item.get('description'):
                text += f" - {item['description']}"
            texts.append(text)
            self.index_to_item[idx] = item
        
        # Generate embeddings
        self.embeddings = self.model.encode(texts)
        
        # Save for later use
        with open(self.embedding_path, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'index_to_item': self.index_to_item
            }, f)
    
    def load_embeddings(self):
        """Load pre-computed embeddings"""
        if self.embedding_path.exists():
            with open(self.embedding_path, 'rb') as f:
                data = pickle.load(f)
                self.embeddings = data['embeddings']
                self.index_to_item = data['index_to_item']
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search for similar constructs/measures"""
        if self.embeddings is None:
            self.load_embeddings()
        
        # Encode query
        query_embedding = self.model.encode([query])
        
        # Calculate similarities
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get top results
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            item = self.index_to_item[idx]
            score = similarities[idx]
            results.append((item, score))
        
        return results