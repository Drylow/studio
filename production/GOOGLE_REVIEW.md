# Examen du refus Google — Edgerunners Studio

État confirmé le 6 octobre 2026 : le parcours officiel du site utilise le client
du projet existant, un état à usage unique, l’accès permanent et la permission
`youtube.force-ssl`. Le nouvel essai réel affiche toujours « This app is blocked ».
Cage Dispatch et Pitch Dispatch ne sont pas connectées. Aucun envoi réel confirmé.

Ce constat concerne le dernier essai du parcours privé puis public. À la demande
de l’utilisateur, une comparaison de la sauvegarde a identifié le parcours gratuit
original (`youtube.upload` + `youtube.readonly`, envoi public direct). Sa compatibilité
est implémentée et documentée dans [LEGACY_YOUTUBE.md](LEGACY_YOUTUBE.md). Un nouveau
consentement réel reste nécessaire. Ne pas proposer à nouveau l’examen Branding
ou un abonnement comme seule prochaine étape.

## Demande d’examen de la propriété du domaine

1. Ouvrir [Branding du projet existant](https://console.cloud.google.com/auth/branding?project=507920096990).
2. Dans Verification status, cliquer **View issues**.
3. Choisir **I believe the issues found are incorrect**, puis **Proceed**.
4. Conserver le résultat affiché par Google. L’envoi d’une demande n’est pas sa validation.

Cette action utilise la session Google du propriétaire, indisponible à l’agent
qui dispose de l’accès Git et o2switch. Ne pas demander son mot de passe Google.
Le refus de propriété est documenté, mais son lien avec le refus OAuth reste inconnu.

Si Google demande une explication, voici un texte prêt à copier :

> Edgerunners Studio is a private channel-management application used by two known
> collaborators. Google Search Console has confirmed DNS ownership of edgerunners.fr,
> but Branding still reports that https://edgerunners.fr/about is not registered to
> us. Our public app information, privacy policy and terms are available at /about,
> /privacy and /terms. Please review the ownership rejection. Separately, the OAuth
> consent flow still shows “This app is blocked” when requesting youtube.force-ssl.
> Please identify whether any project verification or account policy prevents this
> authorization. We have not obtained authorization for the two intended channels.

Avant de revendiquer l’association du compte au projet : Google exige qu’un compte
confirmé propriétaire Search Console soit aussi Owner ou Editor du projet API.
Cette association n’est pas actuellement établie par nos contrôles. Sa confirmation
nécessite la session Google du titulaire ; ne pas inventer un défaut ou sa résolution.

## Justification de la permission, si Google la demande

> Edgerunners Studio lets channel owners prepare and publish their own videos.
> youtube.force-ssl is used to read the authenticated channel ID before uploading,
> upload a checked video privately, set its thumbnail, and update its visibility
> only after our publication checks pass. youtube.upload alone does not authorize
> channels.list or videos.update in the official discovery document. Channel identity
> is checked to prevent uploads to another account. We do not use comment, rating,
> caption or deletion features. Tokens are stored on the private server, never sent
> to the browser, and the owner can disconnect a channel from the studio.

## Limites et résultat nécessaire

- La validation DNS est confirmée par Search Console. Google a indiqué un délai de
  24 heures : prochain contrôle automatique le 7 octobre après 17 h 25 à Paris.
  Ce délai ne concerne que le contrôle Branding et ne garantit pas le déblocage OAuth.
- Google prévoit une exception de revue pour un usage personnel par quelques
  personnes connues. Elle n’autorise pas à franchir un refus ferme.
- Apps Script utilise aussi une autorisation Google et la même API. La documentation
  confirme que même un script publié et utilisé par son propre compte Gmail peut
  suivre le parcours non vérifié. Aucun connecteur Apps Script n’a été installé ou
  testé ; il ne constitue pas une solution confirmée à ce refus.
- Une clé API ne publie pas. Les comptes de service ordinaires ne sont pas pris en
  charge pour les chaînes YouTube personnelles. Les autres parcours OAuth nécessitent
  également le consentement ; ne pas emprunter le client d’une autre application.
- L’approbation OAuth et l’audit d’envoi YouTube sont distincts. Les projets API non
  audités créés après le 28 juillet 2020 peuvent être limités aux vidéos privées.
  Le statut d’audit du projet actuel n’est pas connu.
- La publication sans heure des vidéos prêtes est implémentée et testée. La chaîne
  complète de découverte, vérification, création et publication sans intervention
  reste à terminer. Ni une autorisation ni des tests simulés ne prouvent ce workflow.

Pour conclure à une connexion réussie : consentement réel accepté, jeton permanent
reçu, identité immuable de la bonne chaîne vérifiée via YouTube. Pour conclure à une
publication réussie : véritable envoi autorisé et visibilité confirmée par YouTube.
Conserver la pause et les contrôles de droits jusqu’à ces résultats.

Sources officielles : [propriété et association au projet](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification),
[exception d’usage personnel](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification),
[vérification Apps Script](https://developers.google.com/apps-script/guides/client-verification),
[authentification YouTube](https://developers.google.com/youtube/v3/guides/authentication),
[limites des envois](https://developers.google.com/youtube/v3/docs/videos/insert).
