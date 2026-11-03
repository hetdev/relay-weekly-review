# Weekly review walkthrough

Start the API and UI using the README. The demo clock is fixed at July 28,
2026; timestamps and coverage assumptions are visible in the interface.

1. Select **Pacific Smiles**, **Jul 20–26, 2026**, and **Calls received**.
   The full account has 19 calls against an eight-week mean of 22.375,
   displayed rounded to 22.4. Its baseline counts are
   24, 18, 19, 23, 20, 13, 36 and 26. A change is an investigation cue,
   not a statement about its cause or business health.
2. Expand **Site A** to inspect the baseline and selected-week counts.
   Filter to Site A; the headline then describes that location only.
3. Change to **Leads created**. Counts represent that event type, not unique
   customers or a joined conversion funnel.
4. Reload and use back/forward. Week, account, location and metric filters
   are encoded in the URL and reproduce the selection.
5. Select **Metro Collision Centers** to review a 15-location customer.
   Sort by count/change and expand a row. The server supplies comparison
   labels; the browser only sorts and formats the returned numbers.
6. Select an early February week. Counts remain inspectable while
   insufficient-history labels suppress an unsupported comparison.
7. Select **Quiet Harbor Spa**. Its empty-account state distinguishes no
   recorded activity from a fabricated zero-percent change.

The initial thresholds require a move of at least five events and at least
20% beyond the observed range edge. “Review thresholds not met” can apply
even outside the observed range; it is not a statistical confidence claim.
First recorded activity does not establish when a location opened.

Optional failure demonstration: stop the API, change a filter and observe
the recoverable error. Restart the API, then use **Try again**. No model key
or other external service is needed for the review itself.
