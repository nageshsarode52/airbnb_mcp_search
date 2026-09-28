# Airbnb Stay Finder

The Streamlit interface scrapes Airbnb search results directly and renders the
returned listings and details. The conversational `hotel_search()` agent uses
Groq's `qwen/qwen3-32b` model with the Airbnb search and listing-detail tools.

## Groq setup

1. Create a Groq API key in the [Groq Console](https://console.groq.com/keys).
	The API key is required even when using Groq's no-cost developer tier, which
	has usage limits.
2. Copy `.env.example` to `.env` and set `GROQ_API_KEY` in `.env`. Keep `.env`
	private; it is excluded from Git.
3. Install the project dependencies with `uv sync`.

Run the conversational agent with:

```bash
uv run airbnb_mcp.py
```

Run the Streamlit interface with:

```bash
uv run streamlit run streamlit_app.py
```
