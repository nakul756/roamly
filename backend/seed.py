"""Builds data/travel.db (SQLite) from the CSV plus `places` and `hotels` tables with map coordinates.
Run `python seed.py` after editing the CSV or the lists below (the server also rebuilds automatically when the
schema version changes). ALL COORDINATES ARE APPROXIMATE (hand-entered, good to roughly 100-500 m for sights and
about 1 km for hotels): check them before publishing anything.
Place format:  Name|lat|lon|kind   kinds: sight, museum, food, market, nature, view, beach, park, nightlife
The first places listed for a city are treated as its must-sees."""
import sqlite3

import pandas as pd

from config import BASE, CSV, DB_DIR
import extra_data

DB = DB_DIR / "travel.db"
VERSION = 7

PLACES = """Barcelona: Sagrada Familia|41.4036|2.1744|sight; Park Güell|41.4145|2.1527|park; Barceloneta Beach|41.3784|2.1925|beach; Casa Batlló|41.3917|2.1649|sight; La Boqueria Market|41.3816|2.1719|market; Gothic Quarter|41.3834|2.1767|sight; Montjuïc Castle|41.3637|2.1665|view; Picasso Museum|41.3852|2.1809|museum
Paris: Eiffel Tower|48.8584|2.2945|sight; Louvre Museum|48.8606|2.3376|museum; Sacré-Cœur|48.8867|2.3431|view; Notre-Dame|48.8530|2.3499|sight; Musée d'Orsay|48.8600|2.3266|museum; Arc de Triomphe|48.8738|2.2950|sight; Luxembourg Gardens|48.8462|2.3371|park; Le Marais|48.8575|2.3622|food; Pont Alexandre III|48.8639|2.3135|view; Sainte-Chapelle|48.8554|2.3450|sight
Rome: Colosseum|41.8902|12.4922|sight; Vatican Museums|41.9065|12.4536|museum; Trevi Fountain|41.9009|12.4833|sight; Pantheon|41.8986|12.4769|sight; Roman Forum|41.8925|12.4853|sight; Piazza Navona|41.8992|12.4731|sight; Spanish Steps|41.9060|12.4828|sight; Trastevere|41.8896|12.4698|food; Borghese Gallery|41.9142|12.4922|museum; St. Peter's Basilica|41.9022|12.4539|sight
Amsterdam: Rijksmuseum|52.3600|4.8852|museum; Anne Frank House|52.3752|4.8840|museum; Vondelpark|52.3579|4.8686|park; Van Gogh Museum|52.3584|4.8811|museum; Jordaan|52.3744|4.8800|food; Dam Square|52.3731|4.8926|sight; Albert Cuyp Market|52.3555|4.8944|market; Canal cruise from Centraal|52.3791|4.9003|sight; Heineken Experience|52.3578|4.8918|nightlife
Prague: Prague Castle|50.0903|14.4005|sight; Charles Bridge|50.0865|14.4114|sight; Old Town Square|50.0875|14.4213|sight; Wenceslas Square|50.0813|14.4276|sight; Jewish Quarter|50.0903|14.4180|sight; Petřín Hill|50.0833|14.3953|view; Vyšehrad|50.0640|14.4200|sight; Lennon Wall|50.0868|14.4070|sight; Strahov Monastery Library|50.0866|14.3881|museum
Santorini: Oia|36.4618|25.3753|view; Fira|36.4166|25.4320|sight; Red Beach|36.3485|25.3960|beach; Akrotiri|36.3516|25.4036|sight; Amoudi Bay|36.4605|25.3719|food; Imerovigli|36.4300|25.4250|view; Perissa Beach|36.3610|25.4780|beach; Ancient Thera|36.3667|25.4764|sight; Santo Wines|36.3769|25.4231|food
Athens: Acropolis|37.9715|23.7257|sight; Plaka|37.9726|23.7305|food; Ancient Agora|37.9748|23.7216|sight; Acropolis Museum|37.9685|23.7284|museum; Monastiraki Flea Market|37.9760|23.7255|market; Lycabettus Hill|37.9819|23.7431|view; Temple of Olympian Zeus|37.9693|23.7330|sight; Panathenaic Stadium|37.9684|23.7411|sight; National Archaeological Museum|37.9890|23.7326|museum
Dubrovnik: City Walls|42.6417|18.1104|sight; Banje Beach|42.6420|18.1165|beach; Lokrum Island|42.6314|18.1229|nature; Stradun|42.6410|18.1100|sight; Mount Srđ Cable Car|42.6500|18.1103|view; Rector's Palace|42.6402|18.1108|museum; Fort Lovrijenac|42.6410|18.1050|sight; Old Port|42.6397|18.1146|food
Lisbon: Belém Tower|38.6916|-9.2160|sight; Alfama|38.7110|-9.1301|sight; Praça do Comércio|38.7075|-9.1364|sight; Jerónimos Monastery|38.6979|-9.2068|sight; Pastéis de Belém|38.6975|-9.2032|food; São Jorge Castle|38.7139|-9.1334|view; LX Factory|38.7033|-9.1786|market; Miradouro da Senhora do Monte|38.7196|-9.1327|view; Bairro Alto|38.7133|-9.1456|nightlife; Time Out Market|38.7066|-9.1456|food
Vienna: Schönbrunn Palace|48.1845|16.3122|sight; St. Stephen's Cathedral|48.2084|16.3731|sight; Belvedere|48.1915|16.3808|museum; Hofburg Palace|48.2065|16.3660|sight; Naschmarkt|48.1988|16.3626|market; Prater|48.2166|16.3965|park; Albertina|48.2047|16.3685|museum; Vienna State Opera|48.2031|16.3693|sight; Kunsthistorisches Museum|48.2038|16.3618|museum; Café Central|48.2105|16.3655|food
Budapest: Parliament Building|47.5072|19.0457|sight; Fisherman's Bastion|47.5022|19.0348|view; Széchenyi Baths|47.5186|19.0825|nature; Buda Castle|47.4961|19.0396|sight; Chain Bridge|47.4986|19.0433|sight; Great Market Hall|47.4875|19.0585|market; Gellért Hill Citadella|47.4864|19.0462|view; Szimpla Kert ruin bar|47.4997|19.0644|nightlife; St. Stephen's Basilica|47.5009|19.0537|sight; Heroes' Square|47.5149|19.0773|sight
Interlaken: Harder Kulm|46.6986|7.8527|view; Schynige Platte|46.6606|7.9084|view; Höheweg Promenade|46.6863|7.8632|park; Lauterbrunnen Valley|46.5936|7.9086|nature; Trümmelbach Falls|46.5806|7.9004|nature; Grindelwald|46.6242|8.0414|nature; St. Beatus Caves|46.6869|7.7698|nature; Jungfraujoch|46.5475|7.9854|view; Mürren|46.5589|7.8926|view
Zermatt: Zermatt Village|46.0207|7.7491|sight; Gornergrat|45.9833|7.7845|view; Matterhorn Glacier Paradise|45.9392|7.7297|view; Riffelsee|45.9936|7.7589|nature; Sunnegga|46.0090|7.7650|view; Hinterdorf|46.0190|7.7480|sight; Matterhorn Museum|46.0201|7.7473|museum; Gorner Gorge|46.0245|7.7585|nature
Amalfi Coast: Amalfi Cathedral|40.6344|14.6027|sight; Positano|40.6281|14.4844|sight; Ravello|40.6490|14.6119|view; Path of the Gods (Bomerano start)|40.6240|14.5420|nature; Emerald Grotto|40.6217|14.5659|nature; Atrani|40.6410|14.6100|sight; Furore Fjord|40.6194|14.5586|nature; Marina Grande Beach|40.6275|14.4875|beach
Nice: Promenade des Anglais|43.6950|7.2650|sight; Old Town|43.6958|7.2755|sight; Castle Hill|43.6948|7.2800|view; Cours Saleya Market|43.6954|7.2733|market; Matisse Museum|43.7195|7.2760|museum; Port Lympia|43.6954|7.2850|food; Chagall Museum|43.7098|7.2693|museum; Place Masséna|43.6970|7.2706|sight; Villefranche-sur-Mer|43.7040|7.3110|beach; Monte-Carlo Casino (day trip)|43.7396|7.4276|sight
Copenhagen: Nyhavn|55.6798|12.5910|sight; Tivoli Gardens|55.6736|12.5681|park; Rosenborg Castle|55.6858|12.5773|sight; Little Mermaid|55.6929|12.5993|sight; Christiansborg Palace|55.6761|12.5800|sight; Torvehallerne|55.6838|12.5693|market; Freetown Christiania|55.6741|12.6070|nightlife; Round Tower|55.6813|12.5755|view; Amalienborg|55.6841|12.5934|sight; National Museum of Denmark|55.6747|12.5787|museum
Edinburgh: Edinburgh Castle|55.9486|-3.1999|sight; Royal Mile|55.9500|-3.1883|sight; Arthur's Seat|55.9441|-3.1618|nature; Holyrood Palace|55.9526|-3.1722|sight; Calton Hill|55.9553|-3.1822|view; Dean Village|55.9529|-3.2178|sight; Royal Botanic Garden|55.9652|-3.2090|park; National Museum of Scotland|55.9470|-3.1899|museum; Grassmarket|55.9476|-3.1964|nightlife
Reykjavik: Hallgrímskirkja|64.1419|-21.9266|sight; Gullfoss|64.3271|-20.1199|nature; Blue Lagoon|63.8804|-22.4495|nature; Harpa Concert Hall|64.1503|-21.9327|sight; Þingvellir National Park|64.2559|-21.1299|nature; Geysir|64.3104|-20.3024|nature; Sun Voyager|64.1476|-21.9220|sight; Perlan|64.1292|-21.9208|museum; Seljalandsfoss|63.6156|-19.9886|nature
Tromso: Arctic Cathedral|69.6396|19.0229|sight; Fjellheisen Cable Car|69.6358|19.0128|view; Polaria|69.6449|18.9606|museum; Polar Museum|69.6489|18.9622|museum; Mack Brewery|69.6495|18.9560|food; Tromsø Cathedral|69.6489|18.9549|sight; Sommarøy|69.6320|18.0150|nature
Krakow: Wawel Castle|50.0540|19.9352|sight; Main Market Square|50.0617|19.9373|sight; Kazimierz|50.0514|19.9445|food; Schindler's Factory|50.0476|19.9619|museum; St. Mary's Basilica|50.0617|19.9392|sight; Planty Park|50.0640|19.9420|park; Stary Kleparz Market|50.0680|19.9400|market; Wieliczka Salt Mine (day trip)|49.9833|20.0547|sight
Seville: Alcázar|37.3832|-5.9910|sight; Seville Cathedral|37.3861|-5.9926|sight; Plaza de España|37.3772|-5.9869|sight; Santa Cruz|37.3860|-5.9898|food; Metropol Parasol|37.3930|-5.9917|view; Triana|37.3835|-6.0035|food; María Luisa Park|37.3765|-5.9890|park; Torre del Oro|37.3824|-5.9964|sight; Flamenco Dance Museum|37.3898|-5.9920|museum; Casa de Pilatos|37.3896|-5.9894|sight
Bruges: Markt Square|51.2085|3.2246|sight; Rozenhoedkaai|51.2088|3.2250|view; Minnewater Lake|51.1983|3.2223|park; Belfry|51.2087|3.2247|view; Church of Our Lady|51.2025|3.2259|sight; Begijnhof|51.2037|3.2205|sight; Burg Square|51.2090|3.2268|sight; De Halve Maan Brewery|51.2023|3.2246|food; Groeninge Museum|51.2037|3.2271|museum; Windmills at Kruisvest|51.2133|3.2373|view
Berlin: Brandenburg Gate|52.5163|13.3777|sight; Museum Island|52.5169|13.4019|museum; East Side Gallery|52.5050|13.4397|sight; Reichstag|52.5186|13.3762|sight; Checkpoint Charlie|52.5075|13.3904|sight; Holocaust Memorial|52.5139|13.3787|sight; Berlin Wall Memorial|52.5353|13.3903|museum; Tiergarten|52.5145|13.3501|park; Mauerpark|52.5404|13.4024|market; Markthalle Neun|52.5020|13.4310|food
London: Tower of London|51.5081|-0.0759|sight; British Museum|51.5194|-0.1270|museum; Buckingham Palace|51.5014|-0.1419|sight; Westminster Abbey|51.4993|-0.1273|sight; Big Ben|51.5007|-0.1246|sight; Tower Bridge|51.5055|-0.0754|sight; Borough Market|51.5055|-0.0910|market; Tate Modern|51.5076|-0.0994|museum; Hyde Park|51.5073|-0.1657|park; London Eye|51.5033|-0.1196|view; Covent Garden|51.5117|-0.1240|food
Palma de Mallorca: Palma Cathedral|39.5675|2.6484|sight; Bellver Castle|39.5612|2.6256|view; Caló des Moro|39.3248|3.1724|beach; Valldemossa|39.7096|2.6240|sight; Sa Calobra|39.8500|2.7960|nature; La Lonja|39.5700|2.6470|sight; Mercat de l'Olivar|39.5740|2.6500|market; Sóller|39.7667|2.7150|food; Es Trenc Beach|39.3470|2.9950|beach
Munich: Marienplatz|48.1374|11.5755|sight; English Garden|48.1642|11.6056|park; Nymphenburg Palace|48.1584|11.5033|sight; Viktualienmarkt|48.1352|11.5762|market; Hofbräuhaus|48.1376|11.5799|food; Munich Residenz|48.1423|11.5797|museum; Deutsches Museum|48.1300|11.5835|museum; Olympiapark|48.1755|11.5515|park; Frauenkirche|48.1386|11.5736|sight; Neuschwanstein Castle (day trip)|47.5576|10.7498|sight
Chamonix: Chamonix Town|45.9237|6.8694|sight; Aiguille du Midi|45.8786|6.8873|view; Mer de Glace|45.9319|6.9238|nature; Lac Blanc|45.9780|6.8890|nature; Brévent Cable Car|45.9330|6.8420|view; Argentière|45.9810|6.9270|sight; Lac des Gaillands|45.9100|6.8700|nature; Les Houches|45.8900|6.7980|sight"""

# Approximate hotel locations, (destination, hotel_name): lat, lon
HOTELS = {
 ("Barcelona","Hotel Arts Barcelona"):(41.3870,2.1967), ("Barcelona","Generator Barcelona"):(41.3997,2.1640),
 ("Paris","Pullman Paris Tour Eiffel"):(48.8512,2.2915), ("Paris","Generator Paris"):(48.8814,2.3705), ("Paris","Hôtel Henriette"):(48.8352,2.3510),
 ("Rome","Hotel Artemide"):(41.9005,12.4944), ("Rome","The Beehive"):(41.9017,12.5042),
 ("Amsterdam","Hotel V Nesplein"):(52.3688,4.8918), ("Amsterdam","Stayokay Amsterdam Vondelpark"):(52.3600,4.8746),
 ("Prague","Hotel Josef"):(50.0889,14.4285), ("Prague","Czech Inn"):(50.0707,14.4466),
 ("Santorini","Canaves Oia Suites"):(36.4627,25.3768), ("Santorini","Aressana Spa Hotel"):(36.4166,25.4326), ("Santorini","Hostel Anna"):(36.4172,25.4310),
 ("Athens","Hotel Grande Bretagne"):(37.9753,23.7348), ("Athens","Athens Backpackers"):(37.9660,23.7295), ("Athens","Hotel Electra Palace"):(37.9714,23.7313),
 ("Dubrovnik","Hotel Excelsior Dubrovnik"):(42.6420,18.1184), ("Dubrovnik","Hostel Angelina Old Town"):(42.6404,18.1100), ("Dubrovnik","Hotel Lero"):(42.6410,18.1168),
 ("Lisbon","Memmo Alfama"):(38.7114,-9.1303), ("Lisbon","Lisbon Destination Hostel"):(38.7141,-9.1403), ("Lisbon","Pestana Palace"):(38.7027,-9.2012),
 ("Vienna","Hotel Sacher Wien"):(48.2043,16.3693), ("Vienna","Wombat's City Hostel Vienna"):(48.1983,16.3603), ("Vienna","Hotel Wandl"):(48.2070,16.3698),
 ("Budapest","Corinthia Budapest"):(47.5082,19.0722), ("Budapest","Wombat's City Hostel Budapest"):(47.4990,19.0603),
 ("Interlaken","Victoria-Jungfrau Grand Hotel"):(46.6841,7.8558), ("Interlaken","Balmer's Hostel"):(46.6774,7.8579), ("Interlaken","Hotel Interlaken"):(46.6846,7.8580),
 ("Zermatt","The Omnia"):(46.0183,7.7487), ("Zermatt","Hotel Post Zermatt"):(46.0200,7.7490), ("Zermatt","Matterhorn Hostel"):(46.0190,7.7470),
 ("Amalfi Coast","Hotel Santa Caterina"):(40.6317,14.5960), ("Amalfi Coast","Hotel Lidomare"):(40.6342,14.6035), ("Amalfi Coast","Hostel Brikette"):(40.6283,14.4890),
 ("Nice","Hotel Negresco"):(43.6946,7.2587), ("Nice","Hotel Windsor Nice"):(43.6965,7.2632), ("Nice","Hostel Meyerbeer Beach"):(43.6955,7.2603),
 ("Copenhagen","Hotel d'Angleterre"):(55.6806,12.5846), ("Copenhagen","Generator Copenhagen"):(55.6850,12.5830), ("Copenhagen","Wakeup Copenhagen"):(55.6851,12.5865),
 ("Edinburgh","The Balmoral"):(55.9529,-3.1894), ("Edinburgh","Safestay Edinburgh Elm Row"):(55.9577,-3.1809),
 ("Reykjavik","Hotel Borg"):(64.1469,-21.9392), ("Reykjavik","Kex Hostel"):(64.1451,-21.9174), ("Reykjavik","The Reykjavik EDITION"):(64.1499,-21.9345),
 ("Tromso","Scandic Ishavshotel"):(69.6504,18.9618), ("Tromso","Smarthotel Tromsø"):(69.6490,18.9566),
 ("Krakow","Hotel Stary"):(50.0627,19.9378), ("Krakow","Greg & Tom Hostel"):(50.0624,19.9401), ("Krakow","Hotel Copernicus"):(50.0541,19.9373),
 ("Seville","Hotel Alfonso XIII"):(37.3839,-5.9915), ("Seville","Samay Hostel Seville"):(37.3895,-5.9910), ("Seville","Hotel Casa 1800 Sevilla"):(37.3856,-5.9887),
 ("Bruges","Hotel de Orangerie"):(51.2087,3.2294), ("Bruges","Snuffel Hostel"):(51.2118,3.2200), ("Bruges","Hotel de Tuilerieën"):(51.2058,3.2262),
 ("Berlin","Hotel Adlon Kempinski"):(52.5160,13.3795), ("Berlin","Generator Berlin Mitte"):(52.5253,13.3920),
 ("London","The Savoy"):(51.5100,-0.1203), ("London","Generator London"):(51.5266,-0.1275),
 ("Palma de Mallorca","Castillo Hotel Son Vida"):(39.5983,2.6119), ("Palma de Mallorca","Hotel Born"):(39.5757,2.6491),
 ("Munich","Hotel Bayerischer Hof"):(48.1405,11.5710), ("Munich","Wombat's City Hostel Munich"):(48.1403,11.5578), ("Munich","Hotel Torbräu"):(48.1355,11.5800),
 ("Chamonix","Le Hameau Albert 1er"):(45.9220,6.8625),
}

# Extra hotels added in v6 to fill gaps (mostly budget and mid-range for beach/nature/mountain places).
# (destination, hotel, category, price per night EUR). Prices are rough estimates; verified stays "no".
NEW_HOTELS = [
 ("Santorini","Hostel Anna","hostel",40), ("Santorini","Aressana Spa Hotel","mid-range hotel",220),
 ("Dubrovnik","Hostel Angelina Old Town","hostel",50), ("Dubrovnik","Hotel Lero","mid-range hotel",180),
 ("Nice","Hostel Meyerbeer Beach","hostel",45), ("Nice","Hotel Windsor Nice","mid-range hotel",160),
 ("Seville","Samay Hostel Seville","hostel",30), ("Seville","Hotel Casa 1800 Sevilla","mid-range hotel",220),
 ("Palma de Mallorca","Hotel Born","mid-range hotel",190),
 ("Munich","Wombat's City Hostel Munich","hostel",35), ("Munich","Hotel Torbräu","mid-range hotel",200),
 ("Amalfi Coast","Hostel Brikette","hostel",60), ("Amalfi Coast","Hotel Lidomare","mid-range hotel",220),
 ("Tromso","Smarthotel Tromsø","hostel",90),
 ("Krakow","Greg & Tom Hostel","hostel",25), ("Krakow","Hotel Copernicus","luxury hotel",320),
 ("Bruges","Snuffel Hostel","hostel",30), ("Bruges","Hotel de Tuilerieën","luxury hotel",280),
 ("Zermatt","Matterhorn Hostel","hostel",60),
 ("Reykjavik","The Reykjavik EDITION","luxury hotel",450),
 ("Interlaken","Hotel Interlaken","mid-range hotel",280),
 ("Copenhagen","Wakeup Copenhagen","mid-range hotel",130),
 ("Athens","Hotel Electra Palace","mid-range hotel",220),
 ("Vienna","Hotel Wandl","mid-range hotel",170),
 ("Lisbon","Pestana Palace","luxury hotel",350),
 ("Paris","Hôtel Henriette","mid-range hotel",160),
]
LEVEL = {"hostel": (1, "budget"), "mid-range hotel": (2, "mid-range"), "luxury hotel": (3, "luxury")}


def load_destinations():
    """CSV rows plus the v6 extra hotels (each copies its destination's row and changes the hotel fields)."""
    df = pd.read_csv(CSV)
    have = set(zip(df["destination"], df["hotel_name"]))
    rows, nid = [], int(df["id"].max()) + 1
    for dest, hotel, cat, price in NEW_HOTELS:
        if (dest, hotel) in have:
            continue
        r = df[df["destination"] == dest].iloc[0].copy()
        lvl, name = LEVEL[cat]
        r["id"], r["hotel_name"], r["hotel_category"], r["hotel_price_eur"] = nid, hotel, cat, price
        r["budget_level"], r["budget_category"] = lvl, name
        r["cost_per_day_total_eur"] = int(r["daily_spend_eur"]) + price
        r["estimated_trip_cost_eur"] = int(r["cost_per_day_total_eur"]) * int(r["recommended_days"])
        r["verified"], r["notes"] = "no", "added in v6; approximate; check price and hotel details before use"
        rows.append(r)
        nid += 1
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True) if rows else df
    return pd.concat([df, pd.DataFrame(extra_rows(df))], ignore_index=True)


def extra_rows(df):
    """Rows for the v7 cities in backend/extra_data.py (one per stay), in the same columns as the CSV."""
    out, nid = [], int(df["id"].max()) + 1
    for dest, d in extra_data.DESTS.items():
        (country, airport, cur, lang, schengen, ttype, best_for, months, season, temp, crowd, act, rating, daily, rec, high, food, move, tip, desc) = d
        for hotel, cat, price, _, _ in extra_data.STAYS[dest]:
            lvl, name = extra_data.LEVEL[cat]
            out.append({"id": nid, "destination": dest, "country": country, "airport_code": airport, "currency": cur, "language": lang, "schengen": schengen,
                        "trip_type": ttype, "best_for": best_for, "best_months": months, "best_season": season, "avg_temp_c": temp, "crowd_level": crowd,
                        "activity_level": act, "rating": rating, "budget_level": lvl, "budget_category": name, "daily_spend_eur": daily, "hotel_name": hotel,
                        "hotel_category": cat, "hotel_price_eur": price, "cost_per_day_total_eur": daily + price, "recommended_days": rec,
                        "estimated_trip_cost_eur": (daily + price) * rec, "highlights": high, "must_try_food": food, "getting_around": move,
                        "travel_tip": tip, "description": desc, "verified": "no", "notes": "added in v7; approximate; check price and hotel details before use"})
            nid += 1
    return out


ALL_HOTELS = {**HOTELS, **{(d, h[0]): (h[3], h[4]) for d, hs in extra_data.STAYS.items() for h in hs}}


def build():
    df = load_destinations()
    places = []
    for line in (PLACES + "\n" + extra_data.PLACES).strip().splitlines():
        dest, rest = line.split(":", 1)
        for i, p in enumerate(rest.split(";")):
            name, lat, lon, kind = p.strip().rsplit("|", 3)
            places.append((dest.strip(), name.strip(), float(lat), float(lon), kind, i))
    hotels = []
    for (d, h) in zip(df["destination"], df["hotel_name"]):
        lat, lon = ALL_HOTELS[(d, h)]   # KeyError here means a hotel has no coordinates yet: add it above
        hotels.append((d, h, lat, lon))
    con = sqlite3.connect(DB)
    df.to_sql("destinations", con, if_exists="replace", index=False)
    pd.DataFrame(places, columns=["destination", "name", "lat", "lon", "kind", "ord"]).to_sql("places", con, if_exists="replace", index=False)
    pd.DataFrame(hotels, columns=["destination", "hotel_name", "lat", "lon"]).to_sql("hotels", con, if_exists="replace", index=False)
    con.execute(f"PRAGMA user_version={VERSION}")
    con.commit()
    con.close()


def ensure():
    """Build the database if it is missing or was made by an older version of the app."""
    if DB.exists():
        con = sqlite3.connect(DB)
        v = con.execute("PRAGMA user_version").fetchone()[0]
        con.close()
        if v == VERSION:
            return
    build()


if __name__ == "__main__":
    build()
    print("travel.db created")
