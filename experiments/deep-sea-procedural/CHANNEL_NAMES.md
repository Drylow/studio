# Noms de chaîne marine — vérification du 10 octobre 2026

Projet : histoires vraies des fonds marins, ambiance sombre mais belle, narration calme et vidéos de deux heures. Noms anglais explorés comme pour la chaîne précédente ; la langue des futurs scripts reste à confirmer.

## Méthode et limites

Contrôles effectués entre 22 h 55 et 22 h 56, heure de Paris, via **YouTube Data API v3** : `channels.list(part=snippet, forHandle=@...)`, puis cinq recherches `search.list(part=snippet, type=channel, q="Nom exact", maxResults=50)`. Tous les appels consignés ci-dessous ont répondu HTTP 200. La clé privée existante a été utilisée côté serveur ; elle n’a pas été affichée ni exportée.

Une recherche YouTube peut retourner des chaînes apparentées malgré les guillemets. Les homonymes sont donc repérés en comparant les titres retournés après normalisation de la casse, des espaces et de la ponctuation. On conserve le nombre de résultats inspectés et l’existence éventuelle d’une page suivante.

**Aucun résultat pour un arrobas ne garantit sa réservation.** L’identifiant peut être réservé, inaccessible ou changer après le contrôle. Seule sa saisie et son enregistrement dans YouTube Studio confirment la possibilité de l’utiliser. Aucun nom ni compte n’a été créé.

## Présélection vérifiée

Ces quatre identifiants ne renvoient à aucune chaîne dans `channels.list`, et aucun homonyme exact ne figure dans les résultats de recherche inspectés. Ils peuvent être proposés avec cette précision, sans dire « disponibles à 100 % ».

| Nom | Arrobas proposé | Résolution de l’arrobas | Recherche de noms | Intention |
| --- | --- | --- | --- | --- |
| **Depths After Dark** | [@DepthsAfterDark](https://www.youtube.com/@DepthsAfterDark) | HTTP 200 ; 0 chaîne | HTTP 200 ; 0 homonyme exact dans 2 résultats ; aucune page suivante | Le plus explicite : profondeurs marines, mystère, nuit. Trois mots courts. |
| **Below Dusk** | [@BelowDusk](https://www.youtube.com/@BelowDusk) | HTTP 200 ; 0 chaîne | HTTP 200 ; 0 homonyme exact dans 1 résultats ; aucune page suivante | Le plus court et évocateur ; ambiance nocturne, exploration sous la surface. |
| **Abyss Lull** | [@AbyssLull](https://www.youtube.com/@AbyssLull) | HTTP 200 ; 0 chaîne | HTTP 200 ; 0 homonyme exact dans 49 résultats ; aucune page suivante | Le plus orienté sommeil ; associe les abysses à une accalmie. |
| **Quiet Fathoms** | [@QuietFathoms](https://www.youtube.com/@QuietFathoms) | HTTP 200 ; 0 chaîne | HTTP 200 ; 0 homonyme exact dans 50 résultats ; page suivante non inspectée | Le plus maritime et contemplatif ; « fathoms » évoque une mesure de profondeur. |

**Préférence : Depths After Dark**, pour un nom compréhensible qui annonce immédiatement une ambiance. **Below Dusk** si la brièveté prime. Ne produire ni avatar ni bio définitifs avant le choix utilisateur.

## Variante demandée : Abyss After Dark

Contrôle complémentaire le 10 octobre 2026 à **23 h 00, heure de Paris**. Résultat : **déjà utilisé**, et l’arrobas exact est occupé.

- `channels.list(part=snippet, forHandle=@AbyssAfterDark)` : HTTP 200, `totalResults=1` ; chaîne **Abyss After Dark**, arrobas `@abyssafterdark`, ID `UCoQ7wKefDdjOGsUm7CXxIiw` ([chaîne résolue](https://www.youtube.com/channel/UCoQ7wKefDdjOGsUm7CXxIiw)).
- `search.list(part=snippet, type=channel, q="Abyss After Dark", maxResults=50)` : HTTP 200 ; 4 résultats, **2 homonymes exacts**, aucune page suivante. Deuxième homonyme : `UCOSk1ukw-TbHUZaLxPrq4uQ` ([chaîne](https://www.youtube.com/channel/UCOSk1ukw-TbHUZaLxPrq4uQ)).
- L’API établit l’existence de ces chaînes et l’occupation de l’arrobas, pas leur propriétaire. Ne pas attribuer ces comptes à une personne sans autre preuve.
- Le nom est évocateur mais ne peut pas être proposé comme inédit ni libre. **Depths After Dark** reste la proposition précédemment contrôlée sans homonyme trouvé, sous réserve de sa réservation dans YouTube Studio.
- Aucun avatar ni compte n’a été créé ; aucune publication. Ce contrôle ajoute 1 résolution d’arrobas et 1 recherche (budget théorique : 101 unités).

Horodatage API : `2026-10-10T21:00:05.804555+00:00`.

## Noms écartés après contrôle

| Nom testé | Preuve positive ou collision |
| --- | --- |
| Night Fathoms | Arrobas occupé : [@nightfathoms](https://www.youtube.com/channel/UCeh5TgMsRmAA_DcE3unWJvg), chaîne « NightFathoms », `UCeh5TgMsRmAA_DcE3unWJvg`. |
| Drifting Depths | Arrobas occupé : [@driftingdepths](https://www.youtube.com/channel/UCg6hrJIy1HvN7d6_d88Xo4w), chaîne « Drifting Depths », `UCg6hrJIy1HvN7d6_d88Xo4w`. |
| Noctide | Arrobas occupé : [@noctide](https://www.youtube.com/channel/UCvM3ImQriiSJfCNR20NfCHg), chaîne « Noctide », `UCvM3ImQriiSJfCNR20NfCHg`. |
| Abyss Afterhours | Arrobas occupé : [@abyssafterhours](https://www.youtube.com/channel/UCu6onFDtzOmDMPi90cKQzWQ), chaîne « mimi », `UCu6onFDtzOmDMPi90cKQzWQ`. |
| Night Beneath | Arrobas occupé : [@nightbeneath](https://www.youtube.com/channel/UCXXaBN_ldTwI8RJP03wPpOQ), chaîne « NightBeneath », `UCXXaBN_ldTwI8RJP03wPpOQ`. |
| Fathom Tales | Arrobas occupé : [@fathomtales](https://www.youtube.com/channel/UCfTLCPnhqkpbMEc718uLtkA), chaîne « Fathom Creative », `UCfTLCPnhqkpbMEc718uLtkA`. |
| Below Midnight | Arrobas occupé : [@belowmidnight](https://www.youtube.com/channel/UCcS1k_4YsmUN_xFhTWAgjkw), chaîne « BELOW MIDNIGHT », `UCcS1k_4YsmUN_xFhTWAgjkw`. |
| Deep Rest Tales | Arrobas occupé : [@deepresttales](https://www.youtube.com/channel/UC2oVFnZPBfanQCkdnnegIGg), chaîne « Deep Rest Tales », `UC2oVFnZPBfanQCkdnnegIGg`. |
| Deep Reverie | 8 chaînes homonymes exactes trouvées, dont [Deep Reverie](https://www.youtube.com/channel/UCPyCwitE-YimkwmqkSu0_ug). L’arrobas nu ne résout pourtant aucune chaîne : exemple montrant pourquoi les deux contrôles sont nécessaires. |
| Deep Lull | Chaîne homonyme indexée : [Deep Lull](https://www.youtube.com/@Deep_Lull_official) ; recherche web positive. |
| Still Fathoms | Nom déjà utilisé pour une villa à la Barbade ; nombreux résultats vidéo. Écarté pour éviter cette association. |
| Dusk Below | Nom déjà utilisé pour [un jeu indépendant](https://ethansteele06.itch.io/dusk-below). Écarté malgré l’absence de chaîne résolue à cet arrobas. |

## Liens et données reproductibles

- [Documentation officielle : résolution par arrobas](https://developers.google.com/youtube/v3/docs/channels/list#forHandle).
- [Documentation officielle : recherches de chaînes](https://developers.google.com/youtube/v3/docs/search/list).
- Les liens d’arrobas du tableau sont des identifiants proposés, pas des comptes créés ni une preuve de réservation.
- L’accès direct à `www.youtube.com` était refusé depuis l’environnement cloud. Ce refus n’a pas été contourné ; les vérifications décisives utilisent l’API officielle autorisée côté serveur.
- 17 contrôles d’arrobas, incluant le premier essai, et 5 recherches de chaînes ; budget théorique de 517 unités de quota selon les coûts documentés (1 par `channels.list`, 100 par `search.list`). Aucun upload ni action sur les chaînes.

Paramètres des cinq recherches :

```json
[
  {
    "name": "Quiet Fathoms",
    "parameters": {
      "part": "snippet",
      "type": "channel",
      "q": "\"Quiet Fathoms\"",
      "maxResults": 50
    },
    "http_status": 200,
    "returned_items": 50,
    "exact_name_match_count": 0,
    "has_next_page": true
  },
  {
    "name": "Abyss Lull",
    "parameters": {
      "part": "snippet",
      "type": "channel",
      "q": "\"Abyss Lull\"",
      "maxResults": 50
    },
    "http_status": 200,
    "returned_items": 49,
    "exact_name_match_count": 0,
    "has_next_page": false
  },
  {
    "name": "Below Dusk",
    "parameters": {
      "part": "snippet",
      "type": "channel",
      "q": "\"Below Dusk\"",
      "maxResults": 50
    },
    "http_status": 200,
    "returned_items": 1,
    "exact_name_match_count": 0,
    "has_next_page": false
  },
  {
    "name": "Deep Reverie",
    "parameters": {
      "part": "snippet",
      "type": "channel",
      "q": "\"Deep Reverie\"",
      "maxResults": 50
    },
    "http_status": 200,
    "returned_items": 50,
    "exact_name_match_count": 8,
    "has_next_page": false
  },
  {
    "name": "Depths After Dark",
    "parameters": {
      "part": "snippet",
      "type": "channel",
      "q": "\"Depths After Dark\"",
      "maxResults": 50
    },
    "http_status": 200,
    "returned_items": 2,
    "exact_name_match_count": 0,
    "has_next_page": false
  }
]
```

Horodatage API des contrôles d’arrobas : `2026-10-10T20:55:51.327935+00:00`. Horodatage des recherches de noms : `2026-10-10T20:56:19.563943+00:00`.
