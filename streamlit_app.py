import asyncio
import json
import re
from datetime import date, timedelta
from urllib.parse import quote, urlencode, urlsplit

import streamlit as st

from airbnb_scraper import airbnb_listing_details, airbnb_search


def get_airbnb_search_url(response, destination, check_in, check_out, guests, property_type):
    response_text = response if isinstance(response, str) else str(response)
    url_pattern = re.compile(r"https?://(?:www\.)?airbnb\.com/[^\s<>()\]]+", re.IGNORECASE)

    for candidate in url_pattern.findall(response_text):
        candidate = candidate.rstrip(".,!?;:'\"}")
        parsed_url = urlsplit(candidate)
        if (
            parsed_url.netloc.lower() in {"airbnb.com", "www.airbnb.com"}
            and parsed_url.path.startswith("/s/")
        ):
            return candidate

    params = {
        "checkin": check_in.isoformat(),
        "checkout": check_out.isoformat(),
        "adults": guests,
        "children": 0,
        "infants": 0,
        "pets": 0,
    }
    property_type_names = {
        "Entire home": "Entire home/apt",
        "Private room": "Private room",
        "Shared room": "Shared room",
        "Hotel room": "Hotel room",
    }
    if property_type in property_type_names:
        params["room_types[]"] = property_type_names[property_type]

    return (
        f"https://www.airbnb.com/s/{quote(destination, safe='')}/homes?"
        f"{urlencode(params)}"
    )


st.set_page_config(
    page_title="By - Nagesh Sarode | Accommodation search",
    page_icon="Bonami Stay Finder",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #1f302b;
        --muted: #68766f;
        --line: #dce4dc;
        --paper: #fbfcfa;
        --forest: #24594b;
        --coral: #d86f55;
        --soft-green: #edf3ed;
    }
    .stApp {
        color: var(--ink);
        background-color: var(--paper);
        background-image: repeating-linear-gradient(
            0deg, transparent, transparent 39px,
            rgba(36, 89, 75, 0.025) 40px
        );
    }
    .block-container { max-width: 1060px; padding-top: 2.4rem; }
    h1, h2, h3, p, label { color: var(--ink); }
    .brandline {
        display: flex; align-items: center; gap: 10px;
        margin-bottom: 1.6rem; color: var(--forest);
        font-size: 0.86rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; letter-spacing: 0;
    }
    .brandmark {
        display: inline-grid; place-items: center; width: 30px; height: 30px;
        border-radius: 8px; background: var(--forest); color: white;
        font-family: Georgia, serif; font-size: 1.1rem; letter-spacing: 0;
    }
    .intro { margin: 0 0 1.5rem; }
    .intro h1 {
        margin: 0; font-family: Georgia, 'Times New Roman', serif;
        font-size: 2.65rem; font-weight: 500; letter-spacing: 0;
        line-height: 1.08;
    }
    .intro p { margin: 0.5rem 0 0; color: var(--muted); font-size: 1rem; }
    div[data-testid="stForm"] {
        padding: 1.3rem 1.35rem 1.1rem;
        border: 1px solid var(--line); border-radius: 8px;
        background: rgba(255, 255, 255, 0.92);
    }
    div[data-testid="stForm"] label {
        color: var(--muted); font-size: 0.78rem; font-weight: 650;
    }
    div[data-testid="stForm"] input,
    div[data-testid="stForm"] [data-baseweb="input"] > div,
    div[data-testid="stForm"] [data-baseweb="select"] > div {
        border-color: var(--line); border-radius: 6px;
        background-color: #fff !important; color: var(--ink) !important;
    }
    div[data-testid="stForm"] input {
        -webkit-text-fill-color: var(--ink) !important;
    }
    div.stButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stFormSubmitButton"] button * {
        min-height: 2.75rem; border: 0; border-radius: 6px;
        background: var(--forest); color: #fff !important; font-weight: 650;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background: #173f34; color: #fff;
    }
    .results-heading {
        display: flex; align-items: center; gap: 10px;
        margin: 1.7rem 0 0.8rem; font-family: Georgia, serif;
        font-size: 1.45rem; color: var(--ink);
    }
    .results-rule { height: 1px; background: var(--line); margin-bottom: 1rem; }
    .note {
        padding: 0.75rem 0.9rem; border-left: 3px solid var(--coral);
        background: #fff7f3; color: #69483f; border-radius: 0 5px 5px 0;
        font-size: 0.88rem;
    }
    @media (max-width: 700px) {
        .block-container { padding: 1.2rem 1rem 2rem; }
        .intro h1 { font-size: 2.1rem; }
        div[data-testid="stForm"] { padding: 1rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="brandline"><span class="brandmark">S</span> Stayfinder Powered By Bonami Solutions </div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="intro"><h1>Find a place to stay.</h1>'
    '<p>Search Airbnb stays around your next destination.</p></div>',
    unsafe_allow_html=True,
)

with st.form("stay-search", border=False):
    first_row = st.columns([1.5, 1, 1, 0.8])
    destination = first_row[0].text_input(
        "Destination", placeholder="City, region, or landmark"
    )
    check_in = first_row[1].date_input(
        "Check-in", value=date.today() + timedelta(days=14), min_value=date.today()
    )
    check_out = first_row[2].date_input(
        "Check-out", value=date.today() + timedelta(days=17), min_value=date.today()
    )
    guests = first_row[3].number_input("Guests", min_value=1, max_value=16, value=2)

    second_row = st.columns([1, 1, 1.2, 0.8])
    property_type = second_row[0].selectbox(
        "Stay type",
        ["Any type", "Entire home", "Private room", "Shared room", "Hotel room"],
    )
    min_price = second_row[1].number_input(
        "Minimum nightly price", min_value=0, value=0, step=25
    )
    max_price = second_row[2].number_input(
        "Maximum nightly price", min_value=0, value=0, step=25
    )
    second_row[3].markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    submitted = st.form_submit_button(
        "Search stays", type="primary", use_container_width=True
    )

if submitted:
    if not destination.strip():
        st.error("Enter a destination to search.")
    elif check_out <= check_in:
        st.error("Check-out must be after check-in.")
    elif max_price and min_price > max_price:
        st.error("Maximum price must be greater than or equal to minimum price.")
    else:
        st.markdown(
            '<div class="results-heading">Matching Airbnb stays</div>'
            '<div class="results-rule"></div>',
            unsafe_allow_html=True,
        )
        try:
            with st.spinner(f"Searching stays in {destination.strip()}..."):
                raw_results = asyncio.run(
                    airbnb_search.ainvoke(
                        {
                            "location": destination.strip(),
                            "checkin": check_in.isoformat(),
                            "checkout": check_out.isoformat(),
                            "adults": guests,
                            "min_price": min_price or None,
                            "max_price": max_price or None,
                            "property_type": (
                                ""
                                if property_type == "Any type"
                                else property_type.lower().replace(" ", "_")
                            ),
                            "limit": 10,
                        }
                    )
                )
            st.session_state["airbnb_search_results"] = json.loads(raw_results)
            st.session_state["airbnb_search_context"] = {
                "checkin": check_in.isoformat(),
                "checkout": check_out.isoformat(),
                "adults": guests,
            }
            st.session_state.pop("airbnb_search_error", None)
        except Exception as error:
            st.session_state.pop("airbnb_search_results", None)
            st.session_state["airbnb_search_error"] = str(error)

if search_error := st.session_state.get("airbnb_search_error"):
    st.error(f"Airbnb search could not be completed: {search_error}")
    if destination.strip() and check_out > check_in:
        st.link_button(
            "Open this search on Airbnb",
            get_airbnb_search_url(
                search_error,
                destination.strip(),
                check_in,
                check_out,
                guests,
                property_type,
            ),
        )

search_results = st.session_state.get("airbnb_search_results")
if search_results:
    listings = search_results.get("results", [])
    st.markdown(
        f'<div class="results-heading">Top {len(listings)} matching stays</div>'
        '<div class="results-rule"></div>',
        unsafe_allow_html=True,
    )
    st.caption("Listing information is scraped directly from Airbnb's search results.")
    if not listings:
        st.info("No properties of that exact stay type were found in the results checked.")
        st.link_button(
            "Continue searching on Airbnb",
            get_airbnb_search_url(
                "",
                destination.strip(),
                check_in,
                check_out,
                guests,
                property_type,
            ),
        )
    detail_context = st.session_state.get("airbnb_search_context", {})

    for row_start in range(0, len(listings), 2):
        result_columns = st.columns(2)
        for column, listing in zip(result_columns, listings[row_start:row_start + 2]):
            listing_id = listing["id"]
            detail_key = (
                f"airbnb_details_{listing_id}_"
                f"{detail_context.get('checkin')}_{detail_context.get('checkout')}"
            )
            with column, st.container(border=True):
                photos = listing.get("photos", [])
                if photos:
                    st.image(photos[0], use_container_width=True)
                st.subheader(listing.get("title") or "Airbnb stay")
                if listing.get("subtitle"):
                    st.caption(listing["subtitle"])
                price_column, rating_column = st.columns(2)
                price_column.markdown(f"**{listing.get('price') or 'Price unavailable'}**")
                rating_column.caption(f"Rating: {listing.get('rating') or 'Not rated'}")
                badges = listing.get("badges", [])
                if badges:
                    st.caption(" · ".join(badges))
                if listing.get("url"):
                    st.link_button("View on Airbnb", listing["url"], use_container_width=True)

                with st.expander("Full property details"):
                    details = st.session_state.get(detail_key)
                    if details is None:
                        if st.button("Load details", key=f"load_{detail_key}"):
                            try:
                                with st.spinner("Fetching property description and amenities..."):
                                    raw_details = asyncio.run(
                                        airbnb_listing_details.ainvoke(
                                            {
                                                "listing_id": listing_id,
                                                **detail_context,
                                            }
                                        )
                                    )
                                st.session_state[detail_key] = json.loads(raw_details)
                                st.rerun()
                            except Exception as error:
                                st.error(f"Property details could not be loaded: {error}")
                    else:
                        st.caption(
                            f"{details.get('space_type') or details.get('property_type') or 'Stay'}"
                            f" · Capacity: {details.get('guest_capacity') or 'Not listed'}"
                            f" · {details.get('rating') or 'No rating'}"
                            f" ({details.get('review_count') or 0} reviews)"
                        )
                        if details.get("description"):
                            st.text(details["description"])
                        for highlight in details.get("highlights", []):
                            st.markdown(f"**{highlight['title']}**")
                            if highlight.get("detail"):
                                st.caption(highlight["detail"])
                        for group in details.get("amenities", []):
                            st.markdown(f"**{group.get('group') or 'Amenities'}**")
                            amenity_names = [
                                item["name"]
                                if item.get("available", True)
                                else f"{item['name']} (unavailable)"
                                for item in group.get("items", [])
                            ]
                            if amenity_names:
                                st.write(", ".join(amenity_names))
elif not submitted and not st.session_state.get("airbnb_search_error"):
    st.markdown(
        '<div class="note">Search results depend on the availability of the '
        'Airbnb search service.</div>',
        unsafe_allow_html=True,
    )