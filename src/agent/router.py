from src.agent.state import GraphState
from langgraph.graph import END

def route_after_detection(state: GraphState) -> str:
     """
    Routes the graph to the sanitize node if PII entities are detected; 
    otherwise, ends the graph execution.
    """

     detected_entities = state.get("detected_entities", [])

     len_of_detected_entities = len(detected_entities)

     if len_of_detected_entities > 0:
          return "sanitize_text"
     
     return END
