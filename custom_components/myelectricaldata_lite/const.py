"""Constantes de MyElectricalData Lite."""

from datetime import timedelta

DOMAIN = "myelectricaldata_lite"
API_URL = "https://www.v2.myelectricaldata.fr/api"
CONF_SECRET = "client_secret"

# 4 appels par jour et par PDL, loin du quota de 1000.
UPDATE_INTERVAL = timedelta(hours=6)
# Historique importé au premier lancement (l'API accepte jusqu'à 3 ans).
BACKFILL_DAYS = 364
