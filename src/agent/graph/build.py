from src.agent.nodes import detect_pii, sanitize_text
from langgraph.graph import StateGraph, END, START
from src.agent.state import GraphState
from src.agent.router import route_after_detection

def build_workflow():
     """
     Compiles the LangGraph state machine. 
     Connects the PII detection and sanitization nodes with conditional routing.
     """

     graph = StateGraph(GraphState)

     graph.add_node("detect_pii", detect_pii)
     graph.add_node("sanitize_text", sanitize_text)

     graph.add_edge(START,"detect_pii")

     graph.add_conditional_edges("detect_pii", route_after_detection)

     graph.add_edge("sanitize_text", END)

     return graph.compile()
     