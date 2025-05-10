"""Vector embedding utilities for code retrieval"""
import os
from pathlib import Path
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import pickle
import json

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

class CodeEmbedder:
    """Generates and stores embeddings for code files"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.embedding_model = OllamaEmbeddings(
            model="nomic-embed-text",
        )
        
        # Set up cache directory
        self.cache_dir = cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Code splitter for different languages
        self.code_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\nclass ", "\ndef ", "\nfunction ", "\nif ", "\n\n", "\n", " ", ""]
        )
        
        # Vector store
        self.vector_store = None
    
    def embed_codebase(self, project_dir: Path, exclude_dirs: List[str] = None) -> FAISS:
        """Embed all code files in a directory"""
        if exclude_dirs is None:
            exclude_dirs = [".git", "node_modules", "venv", "__pycache__", ".vscode", ".idea"]
        
        # Check if we have cached embeddings
        cache_path = self._get_cache_path(project_dir)
        if cache_path and cache_path.exists():
            try:
                return self._load_from_cache(cache_path)
            except Exception as e:
                print(f"Failed to load cached embeddings: {e}")
        
        # Collect all code files
        all_files = []
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".md", ".txt"]:
            for file_path in project_dir.glob(f"**/*{ext}"):
                # Skip files in excluded directories
                if any(excl in str(file_path) for excl in exclude_dirs):
                    continue
                all_files.append(file_path)
        
        # Load and split documents
        documents = []
        for file_path in all_files:
            try:
                loader = TextLoader(file_path)
                docs = loader.load()
                
                # Add file path metadata
                for doc in docs:
                    doc.metadata["file_path"] = str(file_path.relative_to(project_dir))
                
                # Split the document
                split_docs = self.code_splitter.split_documents(docs)
                documents.extend(split_docs)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        # Create vector store
        vector_store = FAISS.from_documents(documents, self.embedding_model)
        self.vector_store = vector_store
        
        # Cache the embeddings
        if cache_path:
            self._save_to_cache(vector_store, cache_path)
        
        return vector_store
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant code"""
        if not self.vector_store:
            raise ValueError("No vector store available. Call embed_codebase first.")
        
        # Get similar documents
        docs_and_scores = self.vector_store.similarity_search_with_score(query, k=top_k)
        
        # Format results
        results = []
        for doc, score in docs_and_scores:
            results.append({
                "content": doc.page_content,
                "score": float(score),
                "file_path": doc.metadata.get("file_path", "Unknown"),
                "metadata": doc.metadata
            })
        
        return results
    
    def _get_cache_path(self, project_dir: Path) -> Optional[Path]:
        """Get cache path for embeddings"""
        if not self.cache_dir:
            return None
        
        # Create a hash of the project directory to use as cache key
        dir_hash = str(hash(str(project_dir)))
        return self.cache_dir / f"embeddings_{dir_hash}.faiss"
    
    def _save_to_cache(self, vector_store: FAISS, cache_path: Path):
        """Save embeddings to cache"""
        try:
            vector_store.save_local(str(cache_path))
            print(f"Saved embeddings to {cache_path}")
        except Exception as e:
            print(f"Failed to save embeddings: {e}")
    
    def _load_from_cache(self, cache_path: Path) -> FAISS:
        """Load embeddings from cache"""
        vector_store = FAISS.load_local(str(cache_path), self.embedding_model)
        self.vector_store = vector_store
        print(f"Loaded embeddings from {cache_path}")
        return vector_store