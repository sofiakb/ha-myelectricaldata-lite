"""Constantes de MyElectricalData Lite."""

from datetime import timedelta

DOMAIN = "myelectricaldata_lite"
API_URL = "https://www.v2.myelectricaldata.fr/api"
CONF_SECRET = "client_secret"
CONF_KIND = "kind"
KIND_LINKY = "linky"
KIND_GAZPAR = "gazpar"

# 4 appels par jour et par compteur ; GRDF ne publie qu'une fois par jour.
UPDATE_INTERVAL = {KIND_LINKY: timedelta(hours=6), KIND_GAZPAR: timedelta(hours=12)}
# Historique importé (les API refusent au-delà de 3 ans), par tranches d'un an.
HISTORY_DAYS = 1090
CHUNK_DAYS = 365
# À incrémenter pour forcer une reconstruction complète de l'historique.
HISTORY_VERSION = 3
CONF_HISTORY_VERSION = "history_version"
