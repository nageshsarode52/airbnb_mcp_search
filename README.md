# Airbnb Stay Finder

The Streamlit interface scrapes Airbnb search results directly and renders the
returned listings and details. The conversational `hotel_search()` agent uses
Groq's `qwen/qwen3-32b` model with the Airbnb search and listing-detail tools.

## Groq setup

1. Create a Groq API key in the [Groq Console](https://console.groq.com/keys).
	The API key is required even when using Groq's no-cost developer tier, which
	has usage limits.
2. For local development, copy `.env.example` to `.env` and set `GROQ_API_KEY`.
	For Streamlit Community Cloud, open the app's **Settings > Secrets** and add:

	```toml
	GROQ_API_KEY = "your-groq-api-key"
	```

	Keep the key in Streamlit Secrets or the ignored local `.env`; never commit it.
3. Install the project dependencies with `uv sync`.

The Streamlit listing search currently scrapes Airbnb directly and does not need
the Groq key. The key is used by the conversational `hotel_search()` agent.

Run the conversational agent with:

```bash
uv run airbnb_mcp.py
```

Run the Streamlit interface with:

```bash
uv run streamlit run streamlit_app.py
```
