from src.schemas import DetectedEntity
from typing import TypedDict, List

class GraphState(TypedDict):
     """
    Represents the state of our LangGraph assembly line.
    Every node will read from and write to this state dictionary.
    """

     original_text: str
     detected_entities: List[DetectedEntity]
     sanitized_text: str
    