from src.config import settings
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

def get_llm(temperature: float =0.1):
     """
     Initializes the primary Gemini LLM with a Groq fallback.
     Ensures high availability even if Google's API rate limits are exceeded.
     """

     gemini_llm = ChatGoogleGenerativeAI(
        api_key=SecretStr(settings.GOOGLE_API_KEY),
        model="gemini-2.5-flash",
        temperature=temperature
     )



     groq_llm = ChatGroq(
          api_key=SecretStr(settings.GROQ_API_KEY),
          model="llama-3.3-70b-versatile",
          temperature=temperature
     )

     llm_with_fallback = gemini_llm.with_fallbacks([groq_llm])

     return llm_with_fallback
