# Shanghai offline POI source

`shanghai_pois.json` is the version-controlled source for the demo fact store and
the `shanghai_travel_poi` semantic collection. It contains real Shanghai visitor
destinations, normalized into stable **mock planning values**. Coordinates are
approximate entrance/venue coordinates; hours, prices, reservation flags, and crowd
levels are deliberately non-live snapshots and must not be presented as operational
advice.

The venue selection and descriptive facts were cross-checked against public listings
from the Shanghai Municipal Administration of Culture and Tourism
(https://whlyj.sh.gov.cn/), the Shanghai municipal portal
(https://www.shanghai.gov.cn/), and venue sites including Shanghai Museum
(https://www.shanghaimuseum.net/), Shanghai Disney Resort
(https://www.shanghaidisneyresort.com/), and Shanghai Science and Technology Museum
(https://www.sstm.org.cn/). The dataset is manually curated rather than scraped, so
its build is offline and reproducible.

Run `python scripts/validate_poi_dataset.py` before rebuilding generated SQLite with
`python scripts/init_db.py`. No database file or external embedding output is checked
in.
