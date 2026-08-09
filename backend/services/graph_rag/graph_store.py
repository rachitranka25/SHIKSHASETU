import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

logger = logging.getLogger(__name__)

class GraphStore:
    """
    Manages the Knowledge Graph for GraphRAG using NetworkX.
    Supports local persistence via pickle and semantic traversal.
    """

    def __init__(self, persist_dir: str = "storage/graph"):
        self.persist_dir = persist_dir
        self.graph_path = os.path.join(self.persist_dir, "knowledge_graph.pkl")
        self.graph = nx.DiGraph()
        
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)
            
        self.load_graph()

    def load_graph(self) -> None:
        """Load graph from disk if it exists."""
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, "rb") as f:
                    self.graph = pickle.load(f)
                logger.info(f"Loaded Knowledge Graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
            except Exception as e:
                logger.error(f"Failed to load Knowledge Graph: {e}")
                self.graph = nx.DiGraph()

    def save_graph(self) -> None:
        """Persist graph to disk."""
        try:
            with open(self.graph_path, "wb") as f:
                pickle.dump(self.graph, f)
            logger.debug(f"Saved Knowledge Graph: {self.graph.number_of_nodes()} nodes.")
        except Exception as e:
            logger.error(f"Failed to save Knowledge Graph: {e}")

    def add_entity(self, entity_name: str, entity_type: str, metadata: dict = None) -> None:
        """Add an entity (node) to the graph."""
        entity_name = entity_name.lower().strip()
        if not self.graph.has_node(entity_name):
            self.graph.add_node(entity_name, type=entity_type, **(metadata or {}))
        else:
            # Update metadata if exists
            if metadata:
                for k, v in metadata.items():
                    self.graph.nodes[entity_name][k] = v

    def add_relationship(self, source: str, target: str, relationship_type: str, weight: float = 1.0) -> None:
        """Add a relationship (edge) between two entities."""
        source = source.lower().strip()
        target = target.lower().strip()
        
        # Ensure nodes exist
        if not self.graph.has_node(source):
            self.add_entity(source, "unknown")
        if not self.graph.has_node(target):
            self.add_entity(target, "unknown")
            
        self.graph.add_edge(source, target, type=relationship_type, weight=weight)

    def get_subgraph_context(self, entities: List[str], depth: int = 2) -> str:
        """
        Traverse the graph starting from given entities up to `depth`.
        Returns a formatted text string of the relationships for the LLM.
        """
        visited_nodes = set()
        context_lines = []
        
        for entity in entities:
            entity = entity.lower().strip()
            if entity in self.graph:
                # Get ego graph (neighborhood)
                subgraph = nx.ego_graph(self.graph, entity, radius=depth)
                for u, v, data in subgraph.edges(data=True):
                    if (u, v) not in visited_nodes:
                        rel_type = data.get('type', 'related to')
                        context_lines.append(f"- {u.title()} is {rel_type} {v.title()}")
                        visited_nodes.add((u, v))
                        
        if not context_lines:
            return ""
            
        return "Knowledge Graph Context:\n" + "\n".join(context_lines)

# Singleton
_store_instance = None

def get_graph_store() -> GraphStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = GraphStore()
    return _store_instance
