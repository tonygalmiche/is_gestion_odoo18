# Facturation électronique (Factur-X / EN16931)

## Modules concernés

- `is_facturation_electronique` : module InfoSaône, dépend des modules Akretion/OCA ci-dessous.
- `account_invoice_en16931` + `l10n_fr_account_invoice_en16931` (Akretion) : génération du XML Factur-X/EN16931 via un service externe **Saxon Server**.
- `is_gestion_odoo18` : surcharge `_generate_en16931_dict` (`models/account_move.py`) pour corriger un bug.

## Cas 1 (actuel) vs Cas 2

- **Cas 1** (actif) : génération d'une facture Factur-X/EN16931 conforme, **sans** envoi réel via une plateforme agréée (PA/PDP).
- **Cas 2** (module `l10n_fr_einvoicing`, non installé) : Cas 1 + envoi effectif des factures via une PA (ex. SUPER PDP).

## Bug corrigé : `ApplicableHeaderTradeDelivery` non nillable

**Symptôme** : erreur XSD lors de la génération PDF *"The element ... ApplicableHeaderTradeDelivery ... is not nillable"*.

**Cause** : quand une facture n'a pas d'adresse de livraison (`partner_shipping_id` vide), `account_invoice_en16931` ne remplit pas le bloc BG-13 ("Deliver to"), et le générateur XML produit un élément "nillé", invalide en profil *extended*.

**Correctif** : surcharge de `_generate_en16931_dict` dans `is_gestion_odoo18/models/account_move.py` — si pas d'adresse de livraison, on complète BT-70/75-80 avec l'adresse acheteur (BT-44/50-55).

## Warnings BT-34 / BT-49 (validateur SuperPDP)

- **BT-34** = adresse électronique du vendeur (SIRET), **BT-49** = adresse électronique de l'acheteur (annuaire national).
- Vides tant que `l10n_fr_einvoicing` (Cas 2) n'est pas installé et configuré — normal en Cas 1.
- Bloquant uniquement pour un **envoi réel** via une PA, pas pour un Factur-X conforme généré localement.

## Activer le Cas 2 (si besoin un jour)

1. Installer `l10n_fr_einvoicing` (déjà présent en local, dépendance Python `pyfrctc` déjà sur le serveur).
2. Souscrire un compte "Plateforme Agréée" chez **SUPER PDP** (démarche externe, hors code) → obtenir client_id/secret.
3. Configurer dans *Comptabilité → Paramètres → France eInvoicing*.
4. Envoi des factures :
   - **Automatique** seulement si le cron `fr_einvoicing_flow_out_cron` est activé (désactivé par défaut à l'install).
   - **Manuel** toujours possible via les boutons du flow (`Generate` / `Send`), même cron désactivé.
   - À la validation d'une facture client, un `fr.einvoicing.flow` est créé automatiquement (état "created") mais n'est ni généré ni envoyé sans le cron ou une action manuelle.
