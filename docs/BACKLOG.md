# 📋 Backlog — GNL Process

> Suivi des user stories et améliorations. Statuts : `À faire` · `En cours` · `Fait`

---

## US-001 — Résilience de l'auto-génération aux aléas réseau transitoires

**Statut :** ✅ Fait (2026-09-23)
**Priorité :** Haute
**Créée le :** 2026-09-23
**Origine :** Incident du 2026-09-23 ~15h — alerte Telegram « Pass auto generation issue: the read operation timed out »

### User story

> **En tant que** utilisateur du système d'auto-génération 24/7,
> **je veux** que les timeouts réseau transitoires (lecture du quota NLM, appels MCP)
> soient réessayés automatiquement et ne soient pas traités comme des échecs graves,
> **afin de** ne pas recevoir de fausses alertes alarmantes et que la passe se poursuive
> au lieu d'abandonner à la moindre latence réseau.

### Contexte

Le 23 sept vers 15h, une passe d'auto-génération s'est interrompue au tout début
(lecture du quota NLM via `client.get_usage()`) à cause d'un **timeout réseau
transitoire** (« the read operation timed out »). Comportement observé :

- La passe a **abandonné** immédiatement (pas de retry).
- Une alerte Telegram **🚨 « passe échouée »** a été envoyée, alarmante alors qu'il
  n'y avait **rien à réparer** (budget intact à 100 %, aucune perte).
- Vérification a posteriori : `get_quota_status()` refonctionnait normalement quelques
  minutes plus tard → l'incident était bien **transitoire**.

**Cause racine :** dans `gnl_core/quota.py::get_quota_status`, toute exception
non-« code 16 » (session expirée) est re-levée telle quelle. Un `socket.timeout`
remonte donc jusqu'au driver de la passe (`_scheduled_auto_generate`) qui le capte
et alerte comme un échec grave via `alerts.alert('gnl-pass-error', ...)`.

### Critères d'acceptation

- [ ] **Retry automatique** : `get_quota_status()` réessaie 2 à 3 fois (avec petit
      délai, ex. 3s/6s) en cas de timeout réseau avant d'abandonner. Un aléa
      transitoire passe au 2ᵉ ou 3ᵉ essai.
- [ ] **Classification des erreurs** : distinguer 3 cas —
      (a) `session_expired` (code 16) → 🚨 vraie alerte, à réparer ;
      (b) `network_timeout` (transitoire) → ⏳ reprogrammation rapprochée, alerte douce ou aucune ;
      (c) autre erreur → 🚨 alerte.
- [ ] **Reprogrammation rapprochée** : sur timeout persistant après retries, la passe
      se replanifie dans ~2-3 min (au lieu d'abandonner jusqu'à la prochaine fenêtre).
      `compute_next_delay_seconds` route le cas `network_timeout` vers un délai court.
- [ ] **Alerte différenciée** : message « ⏳ Aléa réseau (retry auto) » au lieu de
      « 🚨 passe échouée ». Le 🚨 reste réservé aux vrais problèmes (session expirée,
      Drive inaccessible, erreurs non transitoires).
- [ ] **Tests** : cas retry qui réussit au 2ᵉ essai ; timeout persistant → délai court ;
      classification correcte des 3 types d'erreurs. Zéro consommation de quota (mocks).
- [ ] **Aucune régression** : les vraies alertes (session expirée) restent en 🚨.

### Notes techniques

- Point d'entrée : `gnl_core/quota.py::get_quota_status` (ajouter le retry + un type
  d'erreur `NetworkTimeoutError` ou un retour classifié).
- Driver : `gnl_core/web/app.py::_scheduled_auto_generate` (router l'alerte selon le type).
- Délais : `gnl_core/auto_generate.py::compute_next_delay_seconds` (ajouter le cas timeout).
- Signature du timeout : message contenant `read operation timed out` / `timed out` /
  `socket.timeout` / `DEADLINE_EXCEEDED`.

---

## US-002 — Test à blanc (health-check préventif) la veille + juste avant la passe

**Statut :** À faire
**Priorité :** Haute
**Créée le :** 2026-09-23
**Origine :** Proposition utilisateur suite aux 3 incidents (crash loop, venv LinkedIn disparu, Drive déconnecté)

### User story

> **En tant que** utilisateur du système d'auto-génération 24/7,
> **je veux** un « test à blanc » planifié la veille au soir (18h) et juste avant la
> passe (5h30) qui vérifie toutes les composantes SANS rien générer et m'envoie un
> récap Telegram,
> **afin de** détecter et corriger un problème AVANT la vraie génération, plutôt que
> de le découvrir après coup.

### Critères d'acceptation

- [ ] Fonction `health_check()` en **lecture seule** (zéro consommation de quota) qui
      teste : session NLM valide · budget dispo · venv MCP LinkedIn présent · Drive
      accessible (accès réel, pas `ismount`) · Bedrock joignable · ffmpeg/ffprobe · file en attente.
- [ ] Job scheduler à **18h** (veille) et **~5h30** (avant la passe de 6h).
- [ ] Message Telegram récap : « 🧪 Test à blanc — NLM ✅ · Budget ✅ · LinkedIn ✅ ·
      Drive ✅ · Bedrock ✅ · File: N articles ». Ligne d'action si ❌.
- [ ] Réutilise `gnl_core/alerts.py`. Tests avec composantes mockées.

### Notes techniques

- Nouveau module `gnl_core/health.py` + 2 jobs APScheduler.
- Réutiliser les self-heals existants (venv LinkedIn) et à venir (Drive).

---

## US-003 — Self-heal du montage Google Drive + alerte si livraison échoue

**Statut :** ✅ Fait (2026-09-23)
**Priorité :** Haute
**Créée le :** 2026-09-23
**Origine :** Incident du 2026-09-23 matin — Drive drvfs déconnecté (« No such device »), passe de 6h a généré mais n'a pas livré le fichier combiné ; échec silencieux.

### User story

> **En tant que** utilisateur,
> **je veux** que le montage Google Drive soit vérifié (accès réel) et réparé
> automatiquement au démarrage et avant chaque combine, et être **alerté** si la
> livraison finale échoue,
> **afin de** ne jamais générer des podcasts (consommant du quota) sans les livrer,
> ni découvrir le problème manuellement.

### Critères d'acceptation

- [ ] Vérifier l'accès **réel** au Drive (lecture d'un fichier/dossier), pas seulement
      `os.path.ismount` (qui retourne vrai sur un mount zombie).
- [ ] Self-heal : `umount -l` des mounts empilés + remount frais si inaccessible.
- [ ] Appelé au démarrage (lifespan) et avant chaque combine/finalize.
- [ ] Éviter l'empilement de mounts à chaque redémarrage du service.
- [ ] **Alerte 🚨 Telegram** si le combine/finalize ne peut pas livrer (Drive KO).
- [ ] Tests : accès réel simulé KO → self-heal tenté ; livraison KO → alerte.

### Notes techniques

- `gnl_core/web/app.py::lifespan` (mount actuel sans vérification d'accès réel).
- `gnl_core/combine.py` + `gnl_core/poster.py` (livraison).
- S'inspirer du self-heal venv LinkedIn (`_ensure_linkedin_mcp_venv`).
