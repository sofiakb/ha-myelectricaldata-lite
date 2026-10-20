"""Constantes de MyElectricalData Lite."""

from datetime import timedelta

DOMAIN = "myelectricaldata_lite"
API_URL = "https://www.v2.myelectricaldata.fr/api"
CONF_SECRET = "client_secret"

# 4 appels par jour et par PDL, loin du quota de 1000.
UPDATE_INTERVAL = timedelta(hours=6)
# Historique importé (l'API refuse au-delà de 3 ans), par tranches d'un an.
HISTORY_DAYS = 1090
CHUNK_DAYS = 365
# À incrémenter pour forcer une reconstruction complète de l'historique.
HISTORY_VERSION = 2
CONF_HISTORY_VERSION = "history_version"
