"""Public product and policy documents, without workspace data or credentials."""

from flask import render_template


SUPPORT_EMAIL = "legrandrecap@gmail.com"
UPDATED = "6 octobre 2026"


DOCUMENTS = {
    "about": {
        "title": "Un studio privé pour vos chaînes YouTube",
        "label": "Présentation",
        "intro": "Edgerunners Studio réunit la préparation de vidéos, les tâches et le calendrier de publication dans un espace réservé à son équipe.",
        "sections": [
            ("Préparer et organiser", "L’équipe peut gérer ses chaînes, écrire ses scripts, créer ses vidéos et miniatures, suivre les travaux et préparer ses publications depuis le même studio."),
            ("Connecter une chaîne avec Google", "La connexion utilise directement les services officiels de Google et l’API YouTube. Le titulaire du compte autorise l’accès à sa chaîne sur la page de Google ; Edgerunners Studio ne demande jamais son mot de passe Google. Les autorisations servent à identifier la chaîne et à envoyer les vidéos, leurs titres, descriptions et miniatures, puis à régler leur visibilité."),
            ("Garder le contrôle", "Les publications suivent les demandes et les réglages de la chaîne. Connecter YouTube n’active pas à lui seul la publication automatique. L’accès peut être retiré depuis le studio ou le compte Google."),
            ("Un espace réservé à l’équipe", "Les chaînes, vidéos, calendriers et outils nécessitent une connexion au studio. Cette présentation et les documents de confidentialité et de conditions sont accessibles publiquement."),
        ],
    },
    "privacy": {
        "title": "Politique de confidentialité",
        "label": "Confidentialité",
        "intro": "Cette politique décrit les données traitées par Edgerunners Studio, disponible sur edgerunners.fr, et l’utilisation de sa connexion officielle à YouTube.",
        "sections": [
            ("Données du studio", "Le studio conserve les identifiants et noms des membres, une empreinte de leur mot de passe, leurs sessions, les chaînes ajoutées, tâches, calendriers, messages à l’assistant, scripts, médias et journaux d’activité nécessaires à son fonctionnement. Les cookies de session servent à la connexion et à la protection des requêtes ; aucun outil publicitaire ou de suivi publicitaire n’est intégré à ces pages."),
            ("Données Google et YouTube", "Après votre autorisation auprès de Google, le studio reçoit des jetons d’accès à YouTube et consulte l’identifiant et le nom de la chaîne autorisée. Il conserve le jeton de renouvellement pour permettre les publications ultérieures. Il traite également les informations des vidéos publiées par le studio, dont leur identifiant, titre, description et visibilité. Il ne demande pas l’accès à Gmail, aux contacts ou à Google Drive."),
            ("Utilisation des autorisations", "Ces données servent à associer la bonne chaîne au studio, vérifier l’accès, envoyer les vidéos et miniatures et mettre à jour leurs métadonnées ou leur visibilité selon vos demandes et réglages. La permission YouTube accordée par Google peut être plus large que les opérations effectivement utilisées par le studio. Les données reçues de Google ne sont ni vendues ni utilisées pour la publicité ou l’entraînement de modèles d’intelligence artificielle."),
            ("Hébergement et services utilisés", "Le studio est hébergé chez o2switch. Les publications et les demandes d’autorisation passent directement par Google et YouTube. Les services de génération de texte, d’images ou de voix et les outils de montage configurés par l’équipe peuvent recevoir les contenus nécessaires à une demande de création, notamment les instructions, scripts ou médias fournis. Le contexte envoyé à l’assistant peut comprendre les noms et identifiants des chaînes, tâches et projets du studio. Les jetons OAuth Google ne sont pas transmis à ces services. Lorsqu’une livraison Discord ou un hébergement de vidéo est demandé, le contenu de cette livraison est transmis au service concerné."),
            ("Accès et conservation", "L’accès aux données du studio est limité aux membres autorisés et aux opérations d’administration de l’hébergement. Les fichiers de données et les jetons sont conservés sur le serveur dans des dossiers privés, hors du dossier web public, avec des permissions restreintes. Les échanges avec le site et Google utilisent HTTPS. Les données de travail restent conservées pour l’utilisation du studio et son historique ; des sauvegardes privées peuvent également les contenir."),
            ("Déconnexion et suppression", "Dans Chaînes, ouvrez la chaîne concernée puis utilisez Déconnecter YouTube : le jeton de renouvellement actif est supprimé du studio et l’automatisation de cette chaîne est suspendue. Son nom, son identifiant et son historique restent conservés pour éviter les confusions de chaîne. Vous pouvez aussi retirer l’autorisation dans votre compte Google via le lien ci-dessous. Pour demander l’accès, la correction ou la suppression des données conservées, y compris des sauvegardes concernées, contactez l’administrateur à l’adresse indiquée en bas de page en précisant le compte ou la chaîne concernée. Ne transmettez jamais votre mot de passe ou vos jetons dans cette demande."),
            ("Engagement relatif aux données Google", "L’utilisation et le transfert par Edgerunners Studio des informations reçues des API Google respectent la politique Google API Services User Data Policy, y compris les exigences Limited Use. L’intégration utilise les API YouTube ; les règles de confidentialité de Google s’appliquent également aux services de Google."),
        ],
        "links": [
            ("Retirer l’accès dans votre compte Google", "https://myaccount.google.com/connections"),
            ("Politique de confidentialité de Google", "https://policies.google.com/privacy"),
            ("Google API Services User Data Policy", "https://developers.google.com/terms/api-services-user-data-policy"),
        ],
    },
    "terms": {
        "title": "Conditions d’utilisation",
        "label": "Conditions",
        "intro": "Edgerunners Studio est un outil privé de gestion et de création de contenus pour les membres autorisés de son équipe.",
        "sections": [
            ("Accès au studio", "Chaque membre utilise son accès personnel et protège ses identifiants. Les pages de présentation, de confidentialité et de conditions sont publiques ; leur consultation ne donne aucun accès aux données ou aux outils privés. L’administrateur du studio gère les membres et leurs permissions."),
            ("Chaînes et publications", "Vous devez disposer des droits nécessaires pour connecter et gérer une chaîne. Google vous demande votre autorisation directement. Vous êtes responsable des réglages choisis, de la validation demandée pour votre chaîne et des contenus dont vous demandez la publication. Le mode automatique, lorsqu’il est opérationnel et activé, agit selon ces réglages ; une simple connexion Google ne l’active pas."),
            ("Contenus et droits", "Avant une publication, assurez-vous de l’exactitude des informations et de vos droits sur les images, vidéos, textes, musiques et voix utilisés. Les contenus produits avec une assistance automatisée nécessitent les contrôles appropriés. Une absence de réclamation YouTube ne prouve pas l’existence de droits de réutilisation."),
            ("Services Google et YouTube", "Le studio utilise les services API YouTube. En utilisant cette intégration, vous acceptez également les Conditions d’utilisation de YouTube, accessibles via le lien ci-dessous. Google et YouTube peuvent refuser une autorisation, limiter l’accès ou une publication, ou exiger une nouvelle connexion. Le studio ne contourne pas ces décisions."),
            ("Disponibilité et frais", "La disponibilité dépend notamment de l’hébergement et des API connectées. Une publication ou une génération peut échouer et doit être vérifiée dans le studio. Les services de génération et de montage configurés par l’équipe peuvent engendrer des frais selon leurs propres tarifs et les réglages de budget du studio."),
            ("Retirer un accès ou contacter l’équipe", "Vous pouvez déconnecter YouTube dans la fiche de la chaîne et retirer l’autorisation dans votre compte Google. Pour un problème d’accès ou une demande concernant vos données, contactez l’administrateur à l’adresse indiquée en bas de page. La politique de confidentialité précise les données conservées et les possibilités de suppression."),
        ],
        "links": [
            ("Conditions d’utilisation de YouTube", "https://www.youtube.com/t/terms"),
            ("Retirer l’accès dans votre compte Google", "https://myaccount.google.com/connections"),
        ],
    },
}


def register(app):
    for name, document in DOCUMENTS.items():
        def page(document=document):
            return render_template(
                "public.html", document=document, support_email=SUPPORT_EMAIL,
                updated=UPDATED,
            )

        app.add_url_rule("/" + name, "public_" + name, page, methods=["GET"])
