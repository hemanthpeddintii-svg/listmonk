"""Relevance gate: is a headline about Global Capability Centers (GCCs) in India?   is_relevant(title) -> bool

'GCC' is a collision-prone acronym, so the rules are layered and explicit (first hit wins; `why(title)` returns the rule name):

  DROP (hard)
    municipal   Greater Chennai Corporation: 'Greater Chennai', 'Chennai Corporation', 'GCC' + commissioner/mayor/ward/zone/school/park/
                cemetery/crematorium/dialysis/wellness/councillor/corporation ...
    gulf        Gulf Cooperation Council: 'GCC countries/states/region/summit/central bank/anti-dumping/network/ECM/aviation',
                'India-GCC aviation|trade|FTA|relations', or Gulf place names (Dubai, Saudi, UAE, Qatar ...) with no India context
    retail      store / mall / showroom / flagship items that merely contain the letters GCC
  KEEP
    centre      'capability centre/center(s)', 'global capabilities', 'global in-house centre', 'captive centre'
    gcc-india   'GCC'/'GCCs' (case-sensitive) + India context (India, Indian city/state, crore/lakh/Rs, Nasscom, Naukri, MeitY ...)
    gcc-bare    'GCC' with no Gulf / municipal signal at all
    gcc-work    'GCC'/'GCCs' + workforce/ecosystem words (hiring, layoffs, talent, MNC, captive, offshore, CXO, BFSI ...) and no Gulf word
    tech-hub    tech/engineering/innovation/R&D/digital/delivery/global-business-services CENTRE or HUB (or 'India tech hub') in an Indian
                city/India context, excluding data centres, experience centres, factories, stores, hospitals, labs for sale ...
  everything else -> drop ('no-match').  Plain appointments / results / sports / real-estate stories without one of the KEEP signals are dropped.
"""
import re

I = re.I

# ---- DROP
MUNICIPAL = re.compile(
    r"greater chennai|chennai corporation|chennai municipal|"
    r"\bGCC\b.{0,40}\b(commissioner|mayor|wards?|zones?|schools?|parks?|cemeter\w+|crematori\w+|dialysis|wellness|councillors?|councils?|corporation|sanitation|garbage|"
    r"hoardings?|milling|bylaws?|encroach\w*|potholes?|stray|hawkers?|desilting|storm ?water|local body|civic|municipal|burial|mogappair|marina|buses|flood\w*|monsoon)\b|"
    r"mental health.{0,40}\bGCC\b|\bGCC (workers|staff|council)\b|wellness cent(?:er|re) for GCC|"
    r"\b(commissioner|mayor|councillors?)\b.{0,40}\bGCC\b|\bGCC('s)? \d+ wards|\bGCC urged\b|rains?, GCC|\bGCC (makes|orders|tells|issues|collects|clears|removes)\b", I)
GULF = re.compile(
    r"gulf cooperation|"
    r"\bGCC[ -](countries|nations|states|region|markets?|bloc|members?|central banks?|economies|economy|governments?|airlines?|airports?|routes?|stocks?|bourses?|equity|ecm|dcm|ipos?|"
    r"tourists?|visa|citizens|nationals|residents|real estate|property|pharma\w* market|pharmaceuticals? market)\b|"
    r"\b(aviation|flights?|air india( express)?)\b.{0,40}\bGCC\b|\bGCC\b.{0,30}\b(aviation|flights?)\b|"
    r"\bindia[-–]+GCC[ -](aviation|trade|fta|flights?|relations?|ties|diaspora|cooperation|free trade|corridor|remittances?|capacity|connectivity|travel|economic|investment|migrants?|workers?)\b|"
    r"\bindia[-–\s]+GCC (aviation|trade|fta|flights?|relations?|diaspora|free trade|remittances?|airlines?|capacity)\b|"
    r"\b(anti-dumping|dumping)\b|across (the )?GCC, (asia|us|europe|and|the)|\bGCC, asia\b|\becm\b|\bGCC (and|&|or) (mena|middle east|europe|asia)\b|\b(mena|middle east)[^.]{0,20}\bGCC\b", I)
GULF_PLACE = re.compile(r"\b(saudi|riyadh|jeddah|uae|dubai|abu dhabi|sharjah|qatar|doha|kuwait|oman|muscat|bahrain|emirates|emirati|gulf|khaleej|arab)\b", I)
RETAIL = re.compile(r"\b(flagship store|store at|mall|showroom|supermarket|hypermarket)\b", I)

# ---- KEEP
CENTRE = re.compile(r"capabilit(?:y|ies)\s+cent(?:er|re)s?|global capabilit(?:y|ies)|global\s+in-?house\s+cent(?:er|re)s?|captive\s+(?:cent(?:er|re)s?|units?|operations?)|"
                    r"\bglobal\s+(?:delivery|technology|tech|innovation|business\s+services|services)\s+cent(?:er|re)s?|\bgbs\b.{0,20}india|india.{0,20}\bgbs\b", I)
GCC_BARE = re.compile(r"\bGCCs?\b")
INDIA_CTX = re.compile(r"\b(india|indian|indians|nasscom|zinnov|ansr|naukri|foundit|teamlease|xpheno|quess|crore|lakh|rs\.?\s?\d|inr|₹|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|navi mumbai|"
                       r"delhi|ncr|gurugram|gurgaon|noida|kolkata|ahmedabad|gandhinagar|gift city|coimbatore|kochi|jaipur|indore|vizag|visakhapatnam|thiruvananthapuram|trivandrum|"
                       r"bhubaneswar|lucknow|chandigarh|mohali|nagpur|mysuru|mysore|vadodara|surat|coimbatore|karnataka|telangana|t.?gana|tamil nadu|maharashtra|gujarat|kerala|odisha|andhra|"
                       r"uttar pradesh|rajasthan|madhya pradesh|haryana|punjab|west bengal|bihar|meity|itbt|tier-?[23]|hyd|blr)\b", I)
GCC_WORK = re.compile(r"\b(hiring|hires?|layoffs?|job cuts?|talent|workforce|attrition|salary|salaries|mnc|mncs|multinationals?|captive|offshore|cxo|bfsi|pharma|semiconductor|retail|automotive|"
                      r"leaders?|ai mandate|operating model|build-?operate|bot\b|enablement|advisory|origin|ecosystem|report|survey|headcount|sourcing|vendors?|it services|it firms|capex|real estate|office space|leasing)\b", I)
TECH_HUB = re.compile(r"\b(?:(?:global|india)\s+)?(?:tech(?:nology)?|engineering|innovation|r&d|research(?: and development)?|digital|delivery|development|design|product|analytics|ai|cyber(?:security)?|"
                      r"shared services?|business services?|excellence|operations?|software|capability|global)\s+(?:cent(?:er|re)s?|hubs?|campus(?:es)?)\b|"
                      r"\bindia\s+(?:tech|technology|engineering|innovation|development)\s+(?:hub|cent(?:er|re))\b|\bgcc\s+(?:cent(?:er|re)|hub)\b", I)
TECH_HUB_NOT = re.compile(r"\b(experience\s*(?:cent(?:er|re)|store)|service\s*cent(?:er|re)|call\s*cent(?:er|re)s?|shopping|mall|store|hospital|clinic|diagnostic|college|school|university|exhibition|convention|"
                          r"airport|metro|township|stadium|temple|cinema|restaurant|café|cafe)\b", I)
ANNOUNCE = re.compile(r"\b(open|opens|opened|launch\w*|inaugurat\w+|sets?\s+up|setting up|establish\w*|expand\w*|plans?|to build|builds?|picks|chooses|signs|invests?|leases?|enters?|"
                      r"bets|doubles?|scales?|adds?|appoints?|appointed|names?|named|joins?|head|heads|leads?|hiring|hires?|to hire|announces?|new)\b", I)


BARE_HUB = re.compile(r"\b(cent(?:er|re)s?|hub)\b", I)
BARE_VERB = re.compile(r"\b(opens?|opened|launch\w*|inaugurat\w+|sets?\s+up|establish\w*|expand\w*|scale|scales|bets on|picks|chooses|maiden|first|plans?|onboard|workforce)\b", I)
BARE_NOT = re.compile(r"\b(data|experience|co-?working|wework|health|screening|manufacturing|plant|fab|airport|store|retail|clinic|cabinet|expressway|quantum|policy|minister|firecrackers|booking|"
                      r"shopping|cyber security|cybersecurity|solar|textile|hyperscale|training|skilling|fitness|dialysis|gym|salon|bank branch|service|call|delivery hub of|ice cream|logistics)\b", I)
ECOSYSTEM = re.compile(r"\b(ansr|zinnov|inductus|gcc-as-a-service|offshore (?:tech )?(?:hubs?|cent(?:er|re)s?)|capability footprint|tech hub for|global (?:solutions|business solutions))\b", I)


def why(title):
    t = (title or "").strip()
    if not t: return "empty"
    if MUNICIPAL.search(t): return "drop:municipal"
    has_india = bool(INDIA_CTX.search(t))
    gulfy = bool(GULF.search(t))
    gulf_place = bool(GULF_PLACE.search(t))
    # explicit Gulf phrases win even if 'India' is present (India-GCC aviation, GCC countries ...), unless it's clearly a capability-centre story
    if gulfy and not CENTRE.search(t): return "drop:gulf"
    if gulf_place and not has_india and not CENTRE.search(t): return "drop:gulf-place"
    if CENTRE.search(t): return "keep:centre"
    if GCC_BARE.search(t):
        if RETAIL.search(t): return "drop:retail"
        if has_india: return "keep:gcc-india"
        if not gulf_place and GCC_WORK.search(t): return "keep:gcc-work"
        if not gulf_place: return "keep:gcc-bare"      # bare 'GCC' with no Gulf/municipal signal: overwhelmingly capability centres
        return "drop:gcc-no-context"
    if TECH_HUB.search(t) and has_india and not TECH_HUB_NOT.search(t) and ANNOUNCE.search(t): return "keep:tech-hub"
    if ECOSYSTEM.search(t) and (has_india or re.search(r"ansr|zinnov", t, I)): return "keep:ecosystem"
    if BARE_HUB.search(t) and BARE_VERB.search(t) and has_india and not BARE_NOT.search(t) and not re.search(r"\bdata\b", t, I): return "keep:bare-hub"
    return "drop:no-match"


def is_relevant(title):
    return why(title).startswith("keep")


if __name__ == "__main__":
    import sys, os, psycopg, collections, random
    rows = psycopg.connect(os.environ.get("DATABASE_URL", "postgresql://gcc:gcc@localhost/gcc"), autocommit=True).execute("SELECT id,title FROM articles").fetchall()
    c = collections.Counter(); by = collections.defaultdict(list)
    for i, t in rows:
        w = why(t); c[w] += 1; by[w].append(t)
    print(c)
    random.seed(1)
    for w in sorted(by):
        print("\n##", w)
        for t in random.sample(by[w], min(int(sys.argv[1]) if len(sys.argv) > 1 else 8, len(by[w]))): print("   ", t[:120])
