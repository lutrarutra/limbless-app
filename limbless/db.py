from .core import DBHandler

db_handler = DBHandler("data/database.db", load_sample_data=True)
# db_handler = DBHandler("data/sample_experiment.db", load_sample_data=True)