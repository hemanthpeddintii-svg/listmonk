# companies_public.csv - sources and method

All rows are one entity per parent (domain = parent's primary web domain, unique). No headcounts, founding years or tech stacks are recorded. Blank fields mean unknown. Cities are limited to ones the compiler was reasonably confident of; rows with blank cities are known GCC/captive centres whose city was not substantiated.

Verification: every `domain` was checked with `curl` (HTTPS, browser UA). 260 returned 200, the rest 3xx/403/404/406/429 (bot protection on large corporate sites) or timed out; all domains resolve in DNS. Every `careers_url` returned 2xx/3xx or 403/406 (bot block). Careers URLs are only given where the compiler recalled a real page; the rest are blank.

## Row groups

- Technology (software, hardware, internet, EDA, gaming): compiler knowledge of well-known India development centres / GCCs of US, European and Asian tech multinationals. Rows for Arctic Wolf, Deepwatch, Jaggaer, Acumatica, Billtrust, Isolved, Imagine Learning and NTT DATA also appear in `articles` headlines (Konsulteer, Investment Monitor, People Matters, Express Computer, Chennai Patrika and similar) about GCC openings.
- Financial Services (banks, asset managers, exchanges, payments, credit bureaus, data providers): compiler knowledge; Truist, Citizens Financial Group, First Citizens, U.S. Bancorp, Blackstone, Brookfield, I Squared Capital, Morgan Stanley, Vanguard, Alvarez & Marsal also come from `articles` headlines (Reuters, Bloomberg, Cognizant/Infosys press, Times of India, ET Realty, hrtoday).
- Insurance (insurers, reinsurers, brokers): compiler knowledge; Zurich, Swiss Re, Aon, BMS Group, The Standard, Prudential Financial, MetLife also appear in `articles` headlines.
- Healthcare & Pharma (pharma, medtech, life-science tools, payers, providers, CROs): compiler knowledge; Lilly, Pfizer, Takeda, Merck, Eisai, Zimmer Biomet, Intuitive, Illumina, Waters, HCA Healthcare, Walgreens, Syneos Health, Availity, TruBridge, Reveleer also appear in `articles` headlines.
- Retail & Consumer (retail, CPG, food and beverage, hospitality, agri-trading): compiler knowledge; Best Buy, Costco, Starbucks, McDonald's, Nestle, Kraft Heinz, Carlsberg, Dick's, Abercrombie & Fitch, PUMA, Ashley, Fuel Cycle, OneMagnify also appear in `articles` headlines.
- Automotive: compiler knowledge of captive engineering/IT centres of OEMs and tier-1 suppliers; Schaeffler also appears in an `articles` headline.
- Industrial & Engineering (incl. logistics, shipping, airlines, agri-science, building products): compiler knowledge; Festo, Kuehne+Nagel, Hapag-Lloyd, MODEC, TOYO, DigiKey, Ferguson, Vontier, AGCO, DAMAC also appear in `articles` headlines. DAMAC (real estate) has no better category in the fixed industry set.
- Aerospace & Defence: compiler knowledge; Rolls-Royce, RTX (Pratt & Whitney) also appear in `articles` headlines.
- Semiconductors (chips, equipment, EDA): compiler knowledge; Infineon (GIFT City, per headline) and Micron also appear in `articles` headlines.
- Telecom & Media (telecom, media, information services, publishing, gaming/betting): compiler knowledge; T-Mobile and Flutter also appear in `articles` headlines.
- Energy (oil and gas, oilfield services, power equipment): compiler knowledge.
- Consulting & Services (Big 4 captive delivery centres, strategy firms, research): compiler knowledge; Alvarez & Marsal, Lexitas, Fuel Cycle, OneMagnify also appear in `articles` headlines.

No gated lists (GCC Journal Excel, AIM Research subscriber lists) and no paid enrichment tools were used. Company names from news headlines were used only as names of real organisations; no text was copied.
