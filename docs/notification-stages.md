# Shipment notification stages

The UI and filter share six stable IDs in `app/tracking/stages.py`:
`preparing`, `picked_up`, `in_transit`, `at_delivery_station`,
`out_for_delivery`, `delivered`.

`users/{id}.settings.notifyStages` stores a list of these IDs. Missing or null
means all six (no migration required); `[]` means no shipment updates. The global
`notifyEnabled` and Telegram/Zalo channel switches still apply. Connection tests,
tracking-created confirmations, and partner webhooks are not shipment events and
are unaffected by this filter. Saving settings preserves unrelated top-level keys.

## Classification

Read-only Firebase MCP inspection of `trackingorderhub` on 2026-11-19 covered all
41 tracking documents: 28 SPX, 9 J&T, 4 LEX. No live data was changed or copied into
this repository. Profiles contain codes/semantics, not account or shipment data.

Resolution order: provider description rules → provider event code → provider
numeric milestone → exact common event/milestone name → unknown (`None`).
Never use a shipment's current status to classify historical events.

| Provider | Events | Stage |
| --- | --- | --- |
| SPX | A000, F000, F001 (pickup failed) | preparing |
| SPX | F098, F100 | picked_up |
| SPX | F440, F441, F445, F450, F510, F515, F540, F541, F580 | in_transit |
| SPX | F599 (last-mile hub), F598 (driver assigned) | at_delivery_station |
| SPX | F600 | out_for_delivery |
| SPX | F980 | delivered |
| LEX | cb_pre_accept | preparing |
| LEX | Known cross-border/linehaul/sorting codes listed in profile | in_transit |
| LEX | domestic_package_stationed_in | at_delivery_station |
| LEX | domestic_package_stationed_out, domestic_out_for_delivery, domestic_about_to_deliver, domestic_redelivery, domestic_1st_attempt_failed | out_for_delivery |
| LEX | domestic_delivered | delivered |
| J&T | Actual pickup descriptions / PICKED_UP | picked_up |
| J&T | IN_TRANSIT | in_transit |
| J&T | Description says “đang giao hàng”, even with PROCESSING | out_for_delivery |
| J&T | Signed receipt descriptions / DELIVERED | delivered |

J&T's old parser labels problem parcels as PICKED_UP and sometimes labels signed
receipts PROCESSING. Description rules take precedence to avoid false pickup
notifications. Problem-parcel events remain unknown; the available data cannot
reliably assign them to a stage. Warehouse arrival alone is insufficient to infer
arrival at the final delivery station. LEX raw cross-border codes are mapped
conservatively to transit; confirm carrier semantics before refining them further.

Unknown events (including exceptions outside the six stages) are delivered only
when all six stages are enabled, preserving the existing all-updates behavior.
Partial or empty selections suppress unknown events. Logs contain carrier, event
code and milestone only, never descriptions, phone numbers or addresses.

## Delivery behavior

Each newly discovered event is filtered independently, in chronological order.
Different events in the same stage remain eligible. Event hashes deduplicate both
stored history and duplicates in a provider response. A batch containing mixed
stages sends only its eligible events; messages describe the individual event.

Initial synchronization with no stored events sends only the latest event if
eligible, not a replay of the entire historical timeline. All events and the
latest tracking status still persist when no messages are sent. Partner webhooks
continue to receive new events without this preference filter.

The existing bounded history and notification retry/transaction behavior are
unchanged: this is not an exactly-once delivery mechanism. Once events fall out of
the configured stored history window, the old hash-based logic can rediscover them.

## Adding a code or provider

1. Inspect carrier event codes, milestones and descriptions with read-only tools.
2. Add a `StageProfile` keyed by the provider's `id` to `PROFILES`, or extend its
   `codes` dictionary. Keys are normalized to lowercase. Use explicit codes; do
   not assume every code sharing a prefix means the same thing.
3. Use provider-scoped `rules` only for ambiguous data. A matching rule returning
   `None` explicitly blocks fallback for an unclassifiable event.
4. Add numeric milestone fallbacks only when they have a reliable meaning for
   that provider. LEX's milestone code `0`, for example, means nothing.
5. Add synthetic regression cases to `tests/test_notification_stages.py`. Do not
   commit live documents, personal information, or credentials.

New providers with recognized exact common names can use the common fallback;
otherwise events remain unknown until a profile is added. UI and notification
transport code require no changes to add a provider or event code.

Run tests with `python -m unittest discover -s tests` in an environment with
`requirements.txt` installed. Tests mock Firestore, providers and notification
transports; they never send messages or mutate the live project.
