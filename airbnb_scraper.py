import base64
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urljoin, urlsplit

import httpx
from langchain_core.tools import tool


BASE_URL = "https://www.airbnb.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
PROPERTY_TYPE_IDS = {
    "entire_home": "1",
    "private_room": "2",
    "shared_room": "3",
    "hotel_room": "4",
}
PROPERTY_SPACE_TYPES = {
    "entire_home": "ENTIRE_HOME",
    "private_room": "PRIVATE_ROOM",
    "shared_room": "SHARED_ROOM",
    "hotel_room": "HOTEL_ROOM",
}


class _AirbnbHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.scripts = []
        self.active_form = None
        self.active_script = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.active_form = {"action": attributes.get("action"), "fields": {}}
            self.forms.append(self.active_form)
        elif tag == "input" and self.active_form is not None:
            name = attributes.get("name")
            if name:
                self.active_form["fields"][name] = attributes.get("value", "")
        elif tag == "script":
            self.active_script = {
                "id": attributes.get("id"),
                "chunks": [],
            }
            self.scripts.append(self.active_script)

    def handle_data(self, data):
        if self.active_script is not None:
            self.active_script["chunks"].append(data)

    def handle_endtag(self, tag):
        if tag == "form":
            self.active_form = None
        elif tag == "script":
            self.active_script = None


def _json_from_html(page_html):
    parser = _AirbnbHTMLParser()
    parser.feed(page_html)
    candidates = sorted(
        parser.scripts,
        key=lambda script: script["id"] != "data-deferred-state-0",
    )
    for script in candidates:
        content = "".join(script["chunks"]).strip()
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "niobeClientData" in payload:
            return payload, parser.forms
    return None, parser.forms


def _is_airbnb_host(hostname):
    if not hostname:
        return False
    hostname = hostname.lower()
    return bool(
        re.fullmatch(
            r"(?:www\.)?airbnb\.(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})",
            hostname,
        )
    )


async def _fetch_page_data(url):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()

        for _ in range(3):
            payload, forms = _json_from_html(response.text)
            if payload is not None:
                return payload

            handoff = next(
                (
                    form
                    for form in forms
                    if form.get("action")
                    and "/v2/domain_switch/handoff" in form["action"]
                ),
                None,
            )
            if handoff is None:
                raise RuntimeError(
                    "Airbnb returned a page without embedded listing data or a "
                    "domain-switch form. The page may be temporarily unavailable."
                )

            action_url = urljoin(str(response.url), handoff["action"])
            if not _is_airbnb_host(urlsplit(action_url).hostname):
                raise RuntimeError("Airbnb returned an unexpected domain-switch host.")

            response = await client.post(
                action_url,
                data=handoff["fields"],
                headers={"Referer": str(response.url)},
            )
            response.raise_for_status()

    raise RuntimeError("Airbnb domain switching did not reach a results page.")


def _search_results(payload):
    for entry in payload.get("niobeClientData", []):
        data = entry[1].get("data", {}) if len(entry) > 1 else {}
        results = (
            data.get("presentation", {})
            .get("staysSearch", {})
            .get("results")
        )
        if isinstance(results, dict) and isinstance(results.get("searchResults"), list):
            return results
    raise RuntimeError("Airbnb's page loaded, but no listing results were present.")


def _decode_listing_id(encoded_id):
    if encoded_id:
        try:
            decoded = base64.b64decode(encoded_id).decode("utf-8")
            return decoded.rsplit(":", 1)[-1]
        except (ValueError, UnicodeDecodeError):
            pass
    return str(encoded_id or "")


def _listing_id(result):
    encoded_id = result.get("demandStayListing", {}).get("id")
    if encoded_id:
        decoded_id = _decode_listing_id(encoded_id)
        if decoded_id != encoded_id:
            return decoded_id
    return str(result.get("propertyId", ""))


def _listing_card(result):
    listing = result.get("demandStayListing", {})
    name = (
        listing.get("description", {})
        .get("name", {})
        .get("localizedStringWithTranslationPreference")
    )
    price = result.get("structuredDisplayPrice", {}).get("primaryLine", {})
    coordinate = listing.get("location", {}).get("coordinate", {})
    listing_id = _listing_id(result)
    return {
        "id": listing_id,
        "title": result.get("title") or name or "Airbnb listing",
        "name": name,
        "subtitle": result.get("subtitle"),
        "price": price.get("accessibilityLabel") or price.get("price"),
        "rating": result.get("avgRatingLocalized"),
        "badges": [badge.get("text") for badge in result.get("badges", []) if badge.get("text")],
        "location": coordinate or None,
        "photos": [
            picture["picture"]
            for picture in result.get("contextualPictures", [])[:3]
            if picture.get("picture")
        ],
        "url": f"{BASE_URL}/rooms/{listing_id}" if listing_id else None,
    }


def _localized_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next((text for item in value if (text := _localized_text(item))), None)
    if isinstance(value, dict):
        for key in (
            "localizedStringWithTranslationPreference",
            "localizedString",
            "localizedContent",
            "text",
            "content",
            "title",
        ):
            if key in value:
                text = _localized_text(value[key])
                if text:
                    return text
        for key, nested in value.items():
            if key != "__typename":
                text = _localized_text(nested)
                if text:
                    return text
    return None


def _clean_html(value):
    if not value:
        return None
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _detail_payload(payload):
    for entry in payload.get("niobeClientData", []):
        data = entry[1].get("data", {}) if len(entry) > 1 else {}
        node = data.get("node", {})
        pdp = node.get("pdpPresentation", {})
        if not pdp:
            continue

        descriptions = pdp.get("descriptions", {})
        long_description = descriptions.get("longDescriptionHtml", {})
        ratings = node.get("listingRatingStats", {}).get("overallRatingStats", {})
        amenities = []
        for group in pdp.get("amenities", {}).get("seeAllAmenitiesGroups", []):
            items = [
                {
                    "name": item.get("title"),
                    "available": item.get("available", True),
                }
                for item in group.get("amenities", [])
                if item.get("title")
            ]
            if items:
                amenities.append({"group": group.get("title"), "items": items})

        highlights = []
        for item in pdp.get("highlights", []):
            headline = _localized_text(item.get("headline"))
            body = _localized_text(item.get("body"))
            if headline:
                highlights.append({"title": headline, "detail": body})

        return {
            "id": _decode_listing_id(node.get("id")),
            "title": _localized_text(pdp.get("title")),
            "property_type": node.get("propertyType"),
            "space_type": node.get("spaceType"),
            "guest_capacity": node.get("personCapacity"),
            "rating": ratings.get("ratingAverage"),
            "review_count": ratings.get("ratingCount"),
            "location": _localized_text(pdp.get("localizedLocation")),
            "description": _clean_html(_localized_text(long_description)),
            "highlights": highlights,
            "amenities": amenities,
            "url": (
                f"{BASE_URL}/rooms/{_decode_listing_id(node.get('id'))}"
                if node.get("id")
                else None
            ),
        }
    raise RuntimeError("Airbnb loaded the listing page without listing details.")


def _could_match_type(title, property_type):
    normalized_title = title.lower()
    room_terms = ("room in ", "private room", "shared room", "hotel room")
    if property_type == "entire_home":
        return not any(term in normalized_title for term in room_terms)
    if property_type in {"private_room", "shared_room"}:
        return "room in " in normalized_title or property_type.replace("_", " ") in normalized_title
    if property_type == "hotel_room":
        return "hotel" in normalized_title or "room in " in normalized_title
    return True


async def _fetch_listing_details(listing_id, checkin="", checkout="", adults=2):
    params = {
        key: value
        for key, value in {
            "check_in": checkin,
            "check_out": checkout,
            "adults": adults,
        }.items()
        if value not in (None, "")
    }
    url = f"{BASE_URL}/rooms/{quote(listing_id.strip(), safe='')}?{urlencode(params)}"
    return _detail_payload(await _fetch_page_data(url))


@tool
async def airbnb_search(
    location: str,
    checkin: str = "",
    checkout: str = "",
    adults: int = 2,
    children: int = 0,
    infants: int = 0,
    pets: int = 0,
    min_price: int | None = None,
    max_price: int | None = None,
    property_type: str = "",
    limit: int = 10,
    cursor: str = "",
) -> str:
    """Search Airbnb by location and return listing titles, prices, ratings, previews and URLs.

    Args:
        location: City, neighborhood, or region to search.
        checkin: Optional check-in date in YYYY-MM-DD format.
        checkout: Optional check-out date in YYYY-MM-DD format.
        adults: Number of adult guests.
        children: Number of child guests.
        infants: Number of infants.
        pets: Number of pets.
        min_price: Optional minimum total price filter.
        max_price: Optional maximum total price filter.
        property_type: Optional category: entire_home, private_room, shared_room, or hotel_room.
        limit: Maximum number of listings to return, up to 10.
        cursor: Optional Airbnb pagination cursor.
    """
    slug = re.sub(r"\s+", "-", location.strip().replace(",", "--"))
    params = {
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "children": children,
        "infants": infants,
        "pets": pets,
        "price_min": min_price,
        "price_max": max_price,
        "cursor": cursor,
    }
    params = {key: value for key, value in params.items() if value not in (None, "")}
    normalized_type = property_type.strip().lower().replace(" ", "_")
    if normalized_type in PROPERTY_TYPE_IDS:
        params["room_types[]"] = {
            "entire_home": "Entire home/apt",
            "private_room": "Private room",
            "shared_room": "Shared room",
            "hotel_room": "Hotel room",
        }[normalized_type]

    search_url = f"{BASE_URL}/s/{quote(slug, safe='-')}/homes?{urlencode(params)}"
    payload = await _fetch_page_data(search_url)
    search_data = _search_results(payload)
    requested_limit = max(1, min(limit, 10))
    cards = []
    seen_ids = set()
    expected_space_type = PROPERTY_SPACE_TYPES.get(normalized_type)
    cursors = search_data.get("paginationInfo", {}).get("pageCursors", [])[1:4]

    for page_index in range(4):
        if page_index > 0:
            if page_index - 1 >= len(cursors):
                break
            page_params = {**params, "cursor": cursors[page_index - 1]}
            page_url = f"{BASE_URL}/s/{quote(slug, safe='-')}/homes?{urlencode(page_params)}"
            page_payload = await _fetch_page_data(page_url)
            search_data = _search_results(page_payload)

        for raw_result in search_data["searchResults"]:
            card = _listing_card(raw_result)
            if not card["id"] or card["id"] in seen_ids:
                continue
            seen_ids.add(card["id"])

            if expected_space_type:
                if not _could_match_type(card["title"], normalized_type):
                    continue
                details = await _fetch_listing_details(
                    card["id"], checkin, checkout, adults
                )
                if details.get("space_type") != expected_space_type:
                    continue
                card["space_type"] = details.get("space_type")

            cards.append(card)
            if len(cards) >= requested_limit:
                break

        if len(cards) >= requested_limit or not expected_space_type:
            break

    return json.dumps(
        {
            "location": location,
            "property_type": normalized_type or "any",
            "count": len(cards),
            "results": cards,
            "next_cursor": cursors[page_index] if page_index < len(cursors) else None,
        },
        ensure_ascii=False,
    )


@tool
async def airbnb_listing_details(
    listing_id: str,
    checkin: str = "",
    checkout: str = "",
    adults: int = 2,
) -> str:
    """Fetch public details for one Airbnb listing, including its description, rating, highlights and amenities.

    Args:
        listing_id: Airbnb listing ID.
        checkin: Optional check-in date in YYYY-MM-DD format.
        checkout: Optional check-out date in YYYY-MM-DD format.
        adults: Number of adult guests for the requested stay.
    """
    details = await _fetch_listing_details(listing_id, checkin, checkout, adults)
    return json.dumps(details, ensure_ascii=False)