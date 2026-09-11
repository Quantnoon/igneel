from pathlib import Path
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).with_name(".env"))

def get_openai_model(name: str = "gpt-5.6-luna"):
    model = ChatOpenAI(
        model=name,
        reasoning_effort="none",
        api_key=os.environ["OPENAI_API_KEY"],
    )
    return model
