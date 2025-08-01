# src/ontology/__init__.py
"""Ontology management modules"""
from .loader import OntologyManager
from .querier import SPARQLQuerier

__all__ = ['OntologyManager', 'SPARQLQuerier']