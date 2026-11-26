---
name: google-flights-fare-search
description: Search Google Flights by route and date through the Apify Google Flights Actor (johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search) and get one JSON row per flight with price, airlines, times, stops, layovers and duration, plus route price insights. Use when an agent needs airfare data for a route, a fare comparison, or flight results as JSON or CSV.
---

# Google Flights Fare Search

Google has no public Flights API, so this skill gets fares through a hosted Apify Actor. Give it IATA airport codes and dates and it returns one dataset item per results page, with about 30 flights in an `all_flights` array. Each flight has `price`, `currency`, `airlines`, `departure_time`, `arrival_time`, `stops`, `layover_airports`, `duration_minutes`, `travel_class` and `flight_numbers`. Each page also carries `price_insights` (`lowest_price`, `price_level`, `typical_price_range`, and `price_history` when shown).

Supports one-way, round-trip and multi-city. Filters: max price, max stops (0 = nonstop), airlines, basic-economy exclusion. `currency`, `hl`, `gl` localize results. `max_pages` is the main cost driver.

Not for live flight status or booking.

Requirements: an Apify account, authenticated via `apify login` or the `APIFY_TOKEN` env var. Runs are billed to that account (small per-run fee plus per-page fee).

## Example

Dates must be in the future (YYYY-MM-DD).

```bash
apify actors call "johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search" \
  -i '{"departure_id":"SFO","arrival_id":"CDG","outbound_date":"2027-03-10","return_date":"2027-03-20","max_stops":0,"max_price":900,"currency":"USD","max_pages":1}' \
  --output-dataset --silent
```

Each item is one results page; flatten with `jq '[.[].all_flights[]]'` for one row per flight.

MCP alternative: `https://mcp.apify.com/?tools=actors,docs,johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search`

## Source

- https://github.com/johnisanerd/claude-skill-google-flights-api
- https://apify.com/johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search
