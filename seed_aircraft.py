"""
One-time seed script: inserts B789 aircraft type, a named seat config layout,
a specific airframe (N787AB) assigned to that layout, then assigns the
airframe to the two sample flights.
Run once after init_db() has been called:
    python3 seed_aircraft.py
"""
from pnr import get_connection, init_db

init_db()

conn = get_connection()
with conn:
    conn.execute("""
        INSERT OR IGNORE INTO aircraft_types (aircraft_type, manufacturer, model)
        VALUES ('B789', 'Boeing', '787-9 Dreamliner')
    """)

    conn.execute("""
        INSERT OR IGNORE INTO seat_config_layouts (config_code, aircraft_type, description)
        VALUES ('B789-3CLASS', 'B789', '3-class Dreamliner layout')
    """)

    conn.execute("""
        INSERT OR IGNORE INTO aircraft (aircraft_id, aircraft_type, config_code)
        VALUES ('N787AB', 'B789', 'B789-3CLASS')
    """)

    configs = [
        # cabin_class,    row_first, row_last, seat_columns,                    aisle_after
        ('Business',      1,  12, 'A,C,D,K',                     'A,D'),
        ('Premium Eco',   21, 23, 'A,B,D,E,F,H,J',               'B,F'),
        ('Economy',       31, 51, 'A,B,C,D,E,F,G,H,J',           'C,F'),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO seat_configs
            (config_code, cabin_class, row_first, row_last, seat_columns, aisle_after)
        VALUES ('B789-3CLASS', ?, ?, ?, ?, ?)
    """, configs)

    conn.execute("""
        UPDATE flights SET aircraft_id = 'N787AB'
        WHERE (flight_no = 'AB 123' AND flight_date = '2026-04-07')
           OR (flight_no = 'AB 857' AND flight_date = '2026-04-09')
    """)

conn.close()
print("Seeded B789 aircraft type, B789-3CLASS layout, N787AB airframe, and seat configs.")
