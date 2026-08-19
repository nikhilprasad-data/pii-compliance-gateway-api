from src.agent.state import GraphState
from src.schemas import DetectedEntity
from src.services import get_llm
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List
from src.agent.prompts import DETECT_PII_PROMPT

class PIIExtraction(BaseModel):
     entities: List[DetectedEntity] = Field(description= "List of detected entities")

llm = get_llm()

structured_llm = llm.with_structured_output(PIIExtraction)

def detect_pii(state: GraphState):
     """
    Analyzes the incoming text and detects PII entities.
    """

     try:

          incoming_text = state.get("original_text", "")

          prompt = ChatPromptTemplate.from_messages([
               ("system", DETECT_PII_PROMPT),
               ("human", "{text}")
          ])

          chain = prompt | structured_llm

          result = chain.invoke({"text" : incoming_text})

          return {
               "detected_entities" : result.entities
          }
          
     except Exception as e:
          print(f"Error in detect_pii_node: {e}")
          return {
               "detected_entities" : []
          }
     