import asyncio
import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from airbnb_scraper import airbnb_listing_details, airbnb_search
import promts

project_dir = Path(__file__).resolve().parent
load_dotenv(project_dir / ".env")


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def get_tools():
    return [airbnb_search, airbnb_listing_details]

async def hotel_search(query):
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "Groq API key is missing. Set GROQ_API_KEY in your environment "
            "or in a .env file in the project root."
        )

    model = ChatGroq(model="qwen/qwen3-32b", temperature=0, max_retries=2)
    tools = await get_tools()
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=promts.AIRBNB_PROMPT,
    )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    response = result["messages"][-1].content
    print("========================Out Put=============================")
    print(response)
    return response

if __name__ == "__main__":
    query = "Show me hotels for a party in Pune, India. Also check latest news and weather"
    asyncio.run(hotel_search(query))
