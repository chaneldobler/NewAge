import mysql.connector
import keyring

class Database:
    def __init__(self):
        password = keyring.get_password("database", "wacker")
        self.db_config = {
            'host': 'mysql-lip.phys.ethz.ch',
            'user': 'wacker',
            'password': password,
            'database': 'db_ams'
        }

    def store(self, sample_nr, prep_nr, target_nr, category, value):
        print(f"sample nr: {sample_nr}, prep nr: {prep_nr}, target nr: {target_nr}, category: {category}, value: {value}")
        categories = {
            "reactor_nr", "co2_init", "co2_final", "hydro_init", 
            "hydro_final", "react_time", "weight", "conc_n", 
            "conc_c", "graphitized", "cn_ratio"
        }
        if category not in categories:
            print(f"Error: Invalid column name '{category}'. Update aborted.")
            return False
        query = f"""
            UPDATE db_ams.target_t
            SET {category} = %s
            WHERE sample_nr = %s 
              AND prep_nr = %s 
              AND target_nr = %s
            LIMIT 1;
        """

        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute(query, (value, sample_nr, prep_nr, target_nr))
            conn.commit()

            if cursor.rowcount > 0:
                print(f"Successfully updated '{category}' to '{value}'.")
                return True
            else:
                print(f"'{category}' already contains data or target row was not found. No changes made.")
                return False

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals() and conn.is_connected():
                conn.close()
