# Khata — Monthly Spend Book

A self-contained monthly expense tracker that runs entirely in the browser — no server, no accounts. The whole app is a single file: [`index.html`](index.html).

## Features

- **Log expenses** with amount, description, category (12 built in), date, payment method, and note
- **Monthly view** — flip between months, or jump via the month picker; every chart and stat is scoped to the month on screen
- **Summary tiles** — month total with change vs last month, budget remaining, daily average, and projected month-end spend
- **Charts** — spending by category, day-by-day bars, and a six-month trend (tap a month to jump to it)
- **Budgets** — an overall monthly limit plus optional per-category limits, with pace warnings at 85% and over-limit flags
- **Recurring expenses** — rent, subscriptions, EMIs: define once, they land in every month automatically; deleting one month's entry skips just that month
- **Search, filter and sort** transactions; click a category bar to filter to it
- **Edit and delete** any entry, with undo
- **Export** the month or everything as CSV; full JSON backup and restore for moving devices
- **Currency** auto-detected from your locale (override in Settings)
- **Light & dark themes**, responsive layout, keyboard-accessible charts with tooltips
- **Sample data** mode to explore, clearly banner-flagged and removable in one click

## Data

Everything is stored in the browser's `localStorage` under the key `khata.spendbook.v1`. Nothing leaves the page. Use **Settings → Export backup** to keep a copy or move to another device.

## Running it

Open `index.html` in any modern browser, or serve the folder statically. The page body is written to be embeddable (it is also deployed as a Claude artifact).
