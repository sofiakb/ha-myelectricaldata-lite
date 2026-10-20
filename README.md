# MyElectricalData Lite

Intégration Home Assistant minimale pour la consommation Linky, via la passerelle [MyElectricalData v2](https://www.v2.myelectricaldata.fr).

Faite pour les petites machines (Raspberry Pi 3, 1 Go) : pas d'app, pas de base de données, 4 requêtes par jour.

- Importe la consommation journalière dans les statistiques HA, à la bonne date, pour le tableau de bord Énergie (statistique `myelectricaldata_lite:consommation_<PDL>`).
- Premier lancement : un an d'historique.
- Capteurs : consommation du dernier jour connu (J-1), des 7 derniers jours, date du dernier jour.

## Installation

1. HACS > menu ⋮ > Dépôts personnalisés > ajouter ce dépôt, type « Intégration ».
2. Installer « MyElectricalData Lite », puis redémarrer HA.
3. Paramètres > Appareils et services > Ajouter > MyElectricalData Lite, coller le Client Secret.
4. Paramètres > Tableaux de bord > Énergie > Ajouter une consommation > `Linky <PDL>`.
