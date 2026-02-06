import pandas as pd
import sqlite3
import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
csv_url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
csv_file_name = "api-scrip-master-detailed.csv"
db_file_name = "dhan_instruments.db"
chunk_size = 100000 

def download_csv(url, filename):
    print(f"Downloading data from {url}...")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
    else:
        raise Exception(f"Failed to download file. Status code: {response.status_code}")

def convert_csv_to_db(csv_file, db_file):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS instruments')
    
    print("Converting CSV to SQL Database...")
    for chunk in pd.read_csv(csv_file, chunksize=chunk_size, low_memory=False):
        # Clean column names (remove spaces)
        chunk.columns = [col.strip() for col in chunk.columns]
        
        # Write to DB
        chunk.to_sql('instruments', conn, if_exists='append', index=False)
        print(f"Processed batch of {len(chunk)} rows...")

    # --- UPDATED INDEXING FOR YOUR COLUMNS ---
    print("Creating search index...")
    # We index 'SYMBOL_NAME' because that is what you will search by (e.g., "RELIANCE")
    c.execute('CREATE INDEX idx_symbol ON instruments(SYMBOL_NAME)')
    # We also index 'SECURITY_ID' in case you need to reverse-lookup
    c.execute('CREATE INDEX idx_sec_id ON instruments(SECURITY_ID)')
    conn.commit()
    conn.close()
    print("Database conversion complete.")

def cleanup_csv(filename):
    if os.path.exists(filename):
        os.remove(filename)
        print(f"Deleted temporary file: {filename}")

def update_database():
    download_csv(csv_url, csv_file_name)
    convert_csv_to_db(csv_file_name, db_file_name)
    cleanup_csv(csv_file_name)
    
    # Update config.json with the current timestamp
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
        else:
            config = {}
            
        config["last_database_update"] = datetime.now().isoformat()
        
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        print(f"Updated last_database_update in config.json")
    except Exception as e:
        print(f"Failed to update config.json: {e}")


def smart_search(search_term):
    try:
        conn = sqlite3.connect(db_file_name)
        c = conn.cursor()
        # We use the '%' wildcard for partial matching
        # We search in SYMBOL_NAME, DISPLAY_NAME, and UNDERLYING_SYMBOL for symbol-like inputs
        query = """
            SELECT SECURITY_ID, EXCH_ID, SERIES, INSTRUMENT, SYMBOL_NAME, DISPLAY_NAME, UNDERLYING_SYMBOL, INSTRUMENT_TYPE, MTF_LEVERAGE
            FROM instruments 
            WHERE SYMBOL_NAME LIKE ? 
               OR DISPLAY_NAME LIKE ?
               OR UNDERLYING_SYMBOL LIKE ?
            ORDER BY 
                CASE 
                    WHEN SEGMENT = 'E' THEN 1 
                    WHEN INSTRUMENT_TYPE = 'EQUITY' THEN 2
                    ELSE 3 
                END,
                SYMBOL_NAME ASC
            LIMIT 50
        """
        # Add wildcards to the search term (e.g., "TATA" becomes "%TATA%")
        wildcard_term = f"%{search_term}%"
        
        c.execute(query, (wildcard_term, wildcard_term, wildcard_term))
        rows = c.fetchall()
        conn.close()

        # Return the 9 requested columns with keys matching user request
        return [
            {
                "security_id": row[0],
                "exchange_id": row[1],
                "series": row[2],
                "instrument": row[3],
                "symbol_name": row[4],
                "display_name": row[5],
                "underlying_symbol": row[6],
                "instrument_type": row[7],
                "mtf_leverage": row[8]
            }
            for row in rows
        ]
    except Exception as e:
        return f"Error: {e}"





