# Third-party code in `prices`

- `trade_query.py` (the trade query model) and `trade_http.py` (the rate-limit header parsing) are
  adapted from [NickRyder/PoEQuery](https://github.com/NickRyder/PoEQuery) (`PoEQuery/official_api_query.py`,
  `PoEQuery/x_rate_limiter.py`), MIT, Copyright (c) 2021 Nick Ryder. The licence text is
  `PoEQuery-LICENSE.txt` in this folder and must stay with any copy of those files.
- The filter set was checked against Awakened PoE Trade (MIT, SnosMe/awakened-poe-trade,
  `renderer/src/web/price-check/trade/pathofexile-trade.ts`); no code was copied from it.
