from src.agent.state import GraphState
from src.schemas import DetectedEntity

def detect_pii(state: GraphState):
     """
    Analyzes the incoming text and detects PII entities.
    """

     try:

          incoming_text = state.get("original_text", "")

          mock_entity = DetectedEntity(
               entity_type= "CREDIT_CARD",
               start_index= 12,
               end_index= 28
          )

          dummy_detected_entitiy =  [mock_entity]

          return {
               "detected_entities" : dummy_detected_entitiy
          }
          
     except Exception as e:
          print(f"Error in detect_pii_node: {e}")
          return {
               "detected_entities" : []
          }
     