"""v7 additions: cheaper and lesser-known cities, each with a hostel, a mid-range and a luxury stay.
EVERYTHING HERE IS APPROXIMATE: prices are rough estimates, hotel names and all coordinates were entered by hand
(good to roughly 100-500 m for sights, about 1 km for hotels). Rows are marked verified="no". Check before publishing.

DESTS columns: country, airport, currency, language, schengen, trip_type, best_for, best_months, best_season
(1 winter, 2 spring, 3 summer, 4 autumn), avg_temp_c, crowd, activity (1-3), rating, daily_spend_eur, recommended_days,
highlights, must_try_food, getting_around, travel_tip, description.
STAYS: (hotel name, category, price per night EUR, lat, lon), categories: hostel / mid-range hotel / luxury hotel.
PLACES: "Name|lat|lon|kind;" kinds: sight, museum, food, market, nature, view, beach, park, nightlife."""

DESTS = {
 "Split": ("Croatia", "SPU", "EUR", "Croatian", "yes", "beach", "friends;couples;solo", "May;Jun;Sep", 3, 27, "medium", 2, 4.5, 70, 4,
           "Diocletian's Palace;Riva promenade;Marjan Hill;city beaches", "black risotto;peka;fresh seafood", "walking and local buses; ferries to the islands",
           "Beat the heat and the cruise crowds by exploring the palace early, then swim at Kašjuni or Bačvice.",
           "A living Roman palace on the Adriatic with clear water, island ferries and cheaper stays than Dubrovnik."),
 "Lagos": ("Portugal", "FAO", "EUR", "Portuguese", "yes", "beach", "couples;friends;families", "Jun;Jul;Sep", 3, 26, "medium", 2, 4.6, 60, 5,
           "golden cliffs;sea caves;Ponta da Piedade;Praia Dona Ana", "grilled sardines;cataplana;pastel de nata", "walking; taxis and local trains along the coast",
           "Book a small-boat or kayak trip to the sea caves early in the morning when the water is calm.",
           "Sheltered Algarve beaches under orange cliffs, easy to do on a budget outside peak August."),
 "Valencia": ("Spain", "VLC", "EUR", "Spanish/Valencian", "yes", "beach", "friends;couples;families", "May;Jun;Sep", 3, 25, "medium", 2, 4.5, 60, 4,
              "City of Arts and Sciences;Malvarrosa beach;Turia Gardens;Central Market", "paella valenciana;horchata;fartons", "metro, tram and bike lanes",
              "Cycle the Turia Gardens to the City of Arts and Sciences, then take the tram to the beach.",
              "A big, flat, bikeable city with a real city beach, great food and prices well below Barcelona."),
 "Cinque Terre": ("Italy", "PSA", "EUR", "Italian", "yes", "beach", "couples;friends;solo", "May;Jun;Sep", 2, 24, "high", 3, 4.7, 90, 3,
                  "five clifftop villages;coastal trails;Monterosso beach;sunset at Manarola", "focaccia;pesto;anchovies", "regional train between the villages; ferries",
                  "Stay in a quieter village such as Corniglia or Monterosso and take the early train to beat the day crowds.",
                  "Five colourful fishing villages linked by coastal paths and trains. Busy in summer, magical in May and September."),
 "Porto": ("Portugal", "OPO", "EUR", "Portuguese", "yes", "city", "friends;couples;solo", "Apr;May;Jun;Sep", 2, 22, "medium", 2, 4.7, 60, 4,
           "Ribeira;port wine cellars;Livraria Lello;Dom Luís I Bridge", "francesinha;bacalhau;port wine", "metro, historic trams and walking (steep hills)",
           "Cross the upper deck of Dom Luís I Bridge for the view, and book the cellar tours in Gaia a day ahead.",
           "Hilly, tiled and affordable, with riverside wine cellars and some of the best food-for-money in Europe."),
 "Ljubljana": ("Slovenia", "LJU", "EUR", "Slovene", "yes", "city", "couples;friends;solo", "May;Jun;Sep", 2, 21, "low", 1, 4.6, 60, 3,
               "riverside cafes;Ljubljana Castle;Dragon Bridge;day trip to Lake Bled", "kranjska klobasa;štruklji;Slovenian wine", "walking; the centre is car-free",
               "Use Ljubljana as a calm base: Lake Bled, Postojna Cave and Piran are all day trips.",
               "A small, green, car-free capital that feels like a hidden gem and is easy on the wallet."),
 "Tallinn": ("Estonia", "TLL", "EUR", "Estonian", "yes", "city", "couples;friends;solo", "May;Jun;Aug;Dec", 3, 20, "medium", 1, 4.6, 60, 3,
             "medieval Old Town;Kadriorg;Telliskivi Creative City;Christmas market", "black bread;elk soup;kama", "walking; trams and buses are cheap",
             "Go up to Kohtuotsa and Patkuli viewing platforms at sunset; they are free and quiet.",
             "A perfectly kept medieval town with a modern digital-nomad scene and low prices."),
 "Sofia": ("Bulgaria", "SOF", "BGN", "Bulgarian", "yes", "culture", "solo;friends;couples", "May;Jun;Sep;Oct", 2, 21, "low", 2, 4.3, 40, 3,
           "Alexander Nevsky Cathedral;Serdica ruins;Boyana Church;Vitosha Mountain", "banitsa;shopska salad;rakia", "metro, trams and walking",
           "Bulgaria uses the lev (BGN), so carry a little cash. It is one of Europe's cheapest capitals.",
           "A relaxed capital with Roman ruins, golden-domed churches and a mountain on its doorstep, at very low prices."),
 "Gdansk": ("Poland", "GDN", "PLN", "Polish", "yes", "culture", "friends;couples;solo", "May;Jun;Aug;Sep", 3, 21, "medium", 2, 4.6, 45, 3,
            "Long Market;Crane;Museum of the Second World War;Sopot pier", "pierogi;żurek;amber souvenirs", "walking and trams; trains to Sopot and Gdynia",
            "Add Sopot for the beach and the long wooden pier. It is 20 minutes away by train.",
            "A rebuilt Hanseatic port city with powerful history, amber shops and an easy beach day nearby."),
 "Ghent": ("Belgium", "BRU", "EUR", "Dutch", "yes", "romantic", "couples;friends;solo", "Apr;May;Jun;Sep", 2, 19, "low", 1, 4.6, 80, 3,
           "Graslei and Korenlei;Gravensteen castle;Patershol alleys;canal boat rides", "waterzooi;Belgian chocolate;Ghent mustard", "walking and trams; trains to Bruges and Brussels",
           "Visit on a weekday evening when the canals are lit up and the day-trippers have gone.",
           "Bruges without the crowds: medieval canals, a real castle and a lively student city."),
 "Colmar": ("France", "BSL", "EUR", "French/Alsatian", "yes", "romantic", "couples;families;friends", "Apr;May;Sep;Dec", 4, 17, "medium", 1, 4.7, 80, 2,
            "Little Venice;half-timbered houses;Alsace wine road;Christmas markets", "tarte flambée;choucroute;Alsace Riesling", "walking; rental car or bike for the wine villages",
            "Spend one day cycling or driving the wine road through Eguisheim and Riquewihr.",
            "A storybook Alsace town of canals and timbered houses, quiet outside the Christmas season."),
 "Bled": ("Slovenia", "LJU", "EUR", "Slovene", "yes", "nature", "couples;friends;families", "Jun;Jul;Sep", 3, 24, "medium", 2, 4.7, 70, 3,
          "Lake Bled and its island;Bled Castle;Vintgar Gorge;Lake Bohinj", "kremšnita cream cake;trout;Slovene wine", "walking around the lake; bus from Ljubljana",
          "Walk the 6 km path around the lake and swim in summer. The water is warm enough in July.",
          "An alpine lake with a church island and a clifftop castle. Cheaper and calmer than the Swiss lakes."),
 "Hallstatt": ("Austria", "SZG", "EUR", "German", "yes", "romantic", "couples;solo;friends", "May;Jun;Sep;Oct", 2, 18, "high", 2, 4.7, 90, 2,
               "lakeside village;Skywalk viewpoint;salt mine;Dachstein caves", "fresh lake fish;Kaiserschmarrn;salt-crust dishes", "walking; ferry and bus around the lake",
               "Arrive before 9am or stay overnight; day-trip coaches fill the village from late morning.",
               "A tiny lakeside village under the Dachstein Alps. Small, stunning and very busy at midday."),
}

STAYS = {
 "Split": [("Swanky Mint Hostel", "hostel", 35, 43.5086, 16.4393), ("Hotel Peristil", "mid-range hotel", 150, 43.5084, 16.4395), ("Hotel Cornaro", "luxury hotel", 260, 43.5112, 16.4385)],
 "Lagos": [("Pousada de Juventude de Lagos", "hostel", 28, 37.1010, -8.6695), ("Tivoli Lagos", "mid-range hotel", 130, 37.1086, -8.6755), ("Pestana Alvor Praia", "luxury hotel", 300, 37.1215, -8.5995)],
 "Valencia": [("Home Youth Hostel Valencia", "hostel", 28, 39.4730, -0.3777), ("Hotel Vincci Lys", "mid-range hotel", 110, 39.4715, -0.3735), ("Las Arenas Balneario Resort", "luxury hotel", 300, 39.4668, -0.3226)],
 "Cinque Terre": [("Ostello Corniglia", "hostel", 35, 44.1195, 9.7118), ("Hotel Pasquale", "mid-range hotel", 190, 44.1472, 9.6578), ("Hotel Porto Roca", "luxury hotel", 320, 44.1450, 9.6540)],
 "Porto": [("Gallery Hostel Porto", "hostel", 30, 41.1450, -8.6150), ("Hotel Teatro", "mid-range hotel", 130, 41.1470, -8.6155), ("The Yeatman", "luxury hotel", 420, 41.1380, -8.6165)],
 "Ljubljana": [("Hostel Celica", "hostel", 30, 46.0575, 14.5155), ("Antiq Hotel", "mid-range hotel", 120, 46.0495, 14.5075), ("Grand Hotel Union", "luxury hotel", 180, 46.0540, 14.5030)],
 "Tallinn": [("Tallinn Backpackers", "hostel", 25, 59.4380, 24.7480), ("Nordic Hotel Forum", "mid-range hotel", 90, 59.4350, 24.7500), ("Hotel Telegraaf", "luxury hotel", 200, 59.4370, 24.7455)],
 "Sofia": [("Hostel Mostel", "hostel", 15, 42.7110, 23.3220), ("Hotel Arena di Serdica", "mid-range hotel", 90, 42.6935, 23.3235), ("Sofia Hotel Balkan", "luxury hotel", 200, 42.6963, 23.3226)],
 "Gdansk": [("Good Bye Lenin Hostel", "hostel", 20, 54.3500, 18.6540), ("Hotel Wolne Miasto", "mid-range hotel", 100, 54.3496, 18.6609), ("Hotel Podewils", "luxury hotel", 180, 54.3500, 18.6585)],
 "Ghent": [("Hostel Uppelink", "hostel", 35, 51.0560, 3.7210), ("Harmony Hotel Ghent", "mid-range hotel", 150, 51.0560, 3.7225), ("Boutique Hotel Verhaegen", "luxury hotel", 240, 51.0545, 3.7260)],
 "Colmar": [("Auberge de Jeunesse Colmar", "hostel", 30, 48.0800, 7.3470), ("Hotel Turenne", "mid-range hotel", 110, 48.0765, 7.3470), ("Hotel Le Maréchal", "luxury hotel", 220, 48.0735, 7.3570)],
 "Bled": [("Bled Rose Hostel", "hostel", 35, 46.3670, 14.1050), ("Hotel Triglav Bled", "mid-range hotel", 150, 46.3670, 14.0980), ("Grand Hotel Toplice", "luxury hotel", 280, 46.3695, 14.1079)],
 "Hallstatt": [("Hallstatt Hostel", "hostel", 45, 47.5620, 13.6490), ("Gasthof Zauner", "mid-range hotel", 150, 47.5625, 13.6495), ("Heritage Hotel Hallstatt", "luxury hotel", 280, 47.5622, 13.6493)],
}

PLACES = """Split: Diocletian's Palace|43.5081|16.4402|sight; Riva Promenade|43.5075|16.4410|sight; Marjan Hill|43.5110|16.4160|view; Bačvice Beach|43.4995|16.4465|beach; Bell Tower of St Domnius|43.5083|16.4402|view; Fruit Square|43.5084|16.4380|food; Green Market|43.5086|16.4427|market; Kašjuni Beach|43.5030|16.4020|beach
Lagos: Ponta da Piedade|37.0833|-8.6667|nature; Praia Dona Ana|37.0895|-8.6740|beach; Old Town Walls|37.1010|-8.6730|sight; Praia do Camilo|37.0925|-8.6710|beach; Meia Praia|37.1150|-8.6500|beach; Slave Market Museum|37.1020|-8.6738|museum; Benagil Cave|37.0870|-8.4230|nature; Sagres Fortress|37.0100|-8.9460|sight
Valencia: City of Arts and Sciences|39.4545|-0.3505|sight; Malvarrosa Beach|39.4770|-0.3240|beach; Central Market|39.4739|-0.3792|market; Valencia Cathedral|39.4753|-0.3753|sight; Turia Gardens|39.4650|-0.3620|park; La Lonja de la Seda|39.4743|-0.3786|sight; Albufera Natural Park|39.3300|-0.3450|nature; Carmen Quarter|39.4786|-0.3813|food
Cinque Terre: Vernazza|44.1349|9.6837|sight; Monterosso Beach|44.1465|9.6545|beach; Manarola|44.1076|9.7280|view; Riomaggiore|44.0996|9.7380|sight; Corniglia|44.1195|9.7118|view; Via dell'Amore|44.1000|9.7385|nature; Blue Trail to Vernazza|44.1420|9.6700|nature; Punta Mesco|44.1440|9.6430|view
Porto: Livraria Lello|41.1468|-8.6149|sight; Ribeira|41.1406|-8.6130|sight; Dom Luís I Bridge|41.1397|-8.6094|sight; Port Wine Cellars of Gaia|41.1370|-8.6150|food; São Bento Station|41.1457|-8.6107|sight; Clérigos Tower|41.1457|-8.6146|view; Palácio da Bolsa|41.1415|-8.6162|sight; Foz do Douro|41.1500|-8.6760|beach; Bolhão Market|41.1495|-8.6074|market
Ljubljana: Ljubljana Castle|46.0489|14.5086|sight; Triple Bridge|46.0511|14.5058|sight; Central Market|46.0508|14.5080|market; Dragon Bridge|46.0520|14.5130|sight; Tivoli Park|46.0590|14.4970|park; Metelkova|46.0568|14.5150|nightlife; Prešeren Square|46.0514|14.5060|sight; Riverside Cafes|46.0505|14.5075|food
Tallinn: Toompea Castle|59.4357|24.7390|sight; Alexander Nevsky Cathedral|59.4358|24.7394|sight; Town Hall Square|59.4372|24.7454|sight; St Olaf's Church|59.4423|24.7455|view; Kadriorg Palace|59.4375|24.7915|sight; Telliskivi Creative City|59.4400|24.7240|nightlife; Kohtuotsa Viewing Platform|59.4380|24.7380|view; Estonian Open Air Museum|59.4350|24.6480|museum; Pirita Beach|59.4700|24.8330|beach
Sofia: Alexander Nevsky Cathedral|42.6958|23.3328|sight; Vitosha Boulevard|42.6930|23.3190|food; Boyana Church|42.6440|23.2660|sight; National Palace of Culture|42.6850|23.3190|sight; Central Sofia Market Hall|42.7010|23.3225|market; Vitosha Mountain|42.5630|23.2500|nature; Serdica Ruins|42.6975|23.3240|sight; Banya Bashi Mosque|42.7010|23.3210|sight
Gdansk: Long Market|54.3487|18.6531|sight; Neptune Fountain|54.3486|18.6533|sight; St Mary's Church|54.3498|18.6525|sight; The Crane|54.3510|18.6577|sight; European Solidarity Centre|54.3612|18.6480|museum; Museum of the Second World War|54.3600|18.6590|museum; Mariacka Street|54.3495|18.6550|food; Westerplatte|54.4060|18.6680|sight; Sopot Pier|54.4465|18.5700|beach
Ghent: Gravensteen Castle|51.0572|3.7210|sight; St Bavo's Cathedral|51.0530|3.7270|sight; Graslei and Korenlei|51.0546|3.7210|view; Belfry of Ghent|51.0540|3.7250|view; Patershol|51.0580|3.7240|food; Saint Michael's Bridge|51.0540|3.7185|view; STAM Museum|51.0430|3.7160|museum; Vooruit|51.0450|3.7270|nightlife
Colmar: Little Venice|48.0745|7.3550|view; Unterlinden Museum|48.0793|7.3500|museum; Koïfhus|48.0786|7.3585|sight; Pfister House|48.0792|7.3580|sight; Collegiate Church of St Martin|48.0790|7.3590|sight; Covered Market|48.0775|7.3550|market; House of Heads|48.0788|7.3578|sight; Eguisheim Village|48.0440|7.3050|sight; Haut-Koenigsbourg Castle|48.2490|7.3440|sight
Bled: Lake Bled|46.3639|14.0938|nature; Bled Island|46.3624|14.0900|sight; Bled Castle|46.3688|14.1006|sight; Vintgar Gorge|46.4000|14.0900|nature; Ojstrica Viewpoint|46.3606|14.1070|view; Mala Osojnica Viewpoint|46.3580|14.0810|view; Park Café Cream Cake|46.3665|14.0950|food; Lake Bohinj|46.2800|13.8870|nature
Hallstatt: Market Square|47.5622|13.6493|sight; Skywalk Viewpoint|47.5560|13.6420|view; Salt Mine|47.5590|13.6430|sight; Bone House|47.5620|13.6490|sight; Lake Boat Ride|47.5610|13.6480|nature; Echern Valley|47.5600|13.6340|nature; Waldbach Waterfall|47.5560|13.6320|nature; Dachstein Glacier|47.4750|13.6150|nature"""

LEVEL = {"hostel": (1, "budget"), "mid-range hotel": (2, "mid-range"), "luxury hotel": (3, "luxury")}
