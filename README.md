# MyElectricalData Lite

Intégration Home Assistant minimale pour la consommation Linky, via la passerelle [MyElectricalData v2](https://www.v2.myelectricaldata.fr), et Gazpar, via l'espace client GRDF.

Faite pour les petites machines (Raspberry Pi 3, 1 Go) : pas d'app, pas de base de données, 4 requêtes par jour.

- Importe la consommation journalière dans les statistiques HA, à la bonne date, pour le tableau de bord Énergie (statistique `myelectricaldata_lite:consommation_<PDL>`).
- Premier lancement : jusqu'à 3 ans d'historique.
- Gaz : statistique `myelectricaldata_lite:gaz_<PCE>`, en kWh, sans pandas (connexion GRDF reprise de PyGazpar).
- Capteurs : consommation du dernier jour connu (J-1), des 7 derniers jours, date du dernier jour.

## Installation

1. HACS > menu ⋮ > Dépôts personnalisés > ajouter ce dépôt, type « Intégration ».
2. Installer « MyElectricalData Lite », puis redémarrer HA.
3. Paramètres > Appareils et services > Ajouter > MyElectricalData Lite, choisir Linky (Client Secret) ou Gazpar (e-mail et mot de passe GRDF).
4. Paramètres > Tableaux de bord > Énergie > Ajouter une consommation > `Linky <PDL>`.
