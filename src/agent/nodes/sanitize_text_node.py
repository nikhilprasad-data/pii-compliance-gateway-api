from src.agent.state import GraphState

def sanitize_text(state: GraphState):
     """Applies redaction masking to identified PII entities within the original text."""

     try:

          original_text = state.get("original_text", "")

          detected_entities = state.get("detected_entities", [])

          if not detected_entities:
               return {"sanitized_text" : original_text}

          else:               
               sanitized_text = original_text

               detected_entities.sort(key =lambda x:  x.start_index, reverse= True)

               for entity in detected_entities:
                    s_i = entities.start_index
                    e_i = entities.end_index

                    sanitized_text = sanitized_text[:s_i] + "REDACTED" + sanitized_text[e_i:]
               
               return {
                    "sanitized_text" : sanitized_text
               }
     
     except Exception as e:

          print(f"Error in sanitize_text_node: {e}")
          return {
               "sanitized_text" : ""
          }
