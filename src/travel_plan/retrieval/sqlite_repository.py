import json, sqlite3
from pathlib import Path
from travel_plan.errors import DataUnavailableError
from travel_plan.models.poi import Hotel, POI, Restaurant
from travel_plan.retrieval.database import initialize_database

class SQLiteRepository:
    def __init__(self,path: str|Path, seed_dir: str|Path|None = None, auto_initialize: bool = False):
        self.path=Path(path)
        if not self.path.exists() and auto_initialize:
            if seed_dir is None:
                raise DataUnavailableError("Automatic SQLite initialization requires seed_dir")
            initialize_database(self.path, seed_dir)
        if not self.path.exists():
            raise DataUnavailableError(
                f"SQLite data missing: {self.path}. Run: python scripts/init_db.py"
            )
    def _rows(self,sql,args=()):
        try:
            con=sqlite3.connect(self.path); con.row_factory=sqlite3.Row
            rows=con.execute(sql,args).fetchall(); con.close(); return rows
        except sqlite3.Error as exc: raise DataUnavailableError(f"SQLite query failed: {exc}") from exc
    def get_pois(self,ids:list[int]) -> list[POI]:
        if not ids:return []
        rows=self._rows(f"SELECT * FROM pois WHERE poi_id IN ({','.join('?'*len(ids))})",ids)
        return [POI(**{**dict(r),"opening_hours":json.loads(r["opening_hours"]),
            "tags":json.loads(r["tags"]), "special_dates":json.loads(r["special_dates"]),
            "aliases":json.loads(r["aliases"]),
            "reservation_required":bool(r["reservation_required"]),"outdoor":bool(r["outdoor"]),
            "ticket_required":bool(r["ticket_required"]), "indoor":bool(r["indoor"])}) for r in rows]
    def all_pois(self,city:str)->list[POI]: return self.get_pois([r["poi_id"] for r in self._rows("SELECT poi_id FROM pois WHERE city=?",(city,))])
    def restaurants(self,city:str)->list[Restaurant]:
        return [Restaurant(**{**dict(r),"opening_hours":json.loads(r["opening_hours"])}) for r in self._rows("SELECT restaurant_id,name,cuisine,district,lat,lon,price_per_person,opening_hours FROM restaurants WHERE city=?",(city,))]
    def hotels(self,city:str)->list[Hotel]:
        return [Hotel(**{**dict(r),"supports_luggage_storage":bool(r["supports_luggage_storage"])}) for r in self._rows("SELECT hotel_id,name,district,lat,lon,nightly_price,supports_luggage_storage,check_in_time,check_out_time FROM hotels WHERE city=?",(city,))]
