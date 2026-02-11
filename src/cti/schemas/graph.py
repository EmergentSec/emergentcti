from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    entity_type: str  # "observable" | "threat_actor" | "campaign" | "technique"
    label: str
    metadata: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    metadata: dict = {}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
