from pathlib import Path
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

from agent.paths import ENV_FILE

load_dotenv(ENV_FILE)

def get_openai_model(name: str = "gpt-5.6-luna"):
    model = ChatOpenAI(
        model=name,
        reasoning_effort="none",
        api_key=os.environ["OPENAI_API_KEY"],
    )
    return model
