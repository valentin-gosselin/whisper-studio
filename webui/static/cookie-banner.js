/**
 * Cookie Banner - RGPD Compliant
 * Gère l'affichage et le consentement des cookies
 */

(function() {
    'use strict';

    const COOKIE_CONSENT_KEY = 'cookie_consent';
    const COOKIE_BANNER_DISMISSED_KEY = 'cookie_banner_dismissed';

    /**
     * Vérifie si l'utilisateur a déjà donné son consentement
     */
    function hasConsent() {
        return localStorage.getItem(COOKIE_CONSENT_KEY) === 'accepted' ||
               localStorage.getItem(COOKIE_BANNER_DISMISSED_KEY) === 'true';
    }

    /**
     * Enregistre le consentement
     */
    function saveConsent() {
        localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');
        localStorage.setItem(COOKIE_BANNER_DISMISSED_KEY, 'true');
    }

    /**
     * Ferme la bannière avec animation
     */
    function closeBanner() {
        const banner = document.getElementById('cookieBanner');
        if (banner) {
            banner.classList.remove('show');
            setTimeout(() => {
                banner.remove();
            }, 400);
        }
    }

    /**
     * Accepte les cookies et ferme la bannière
     */
    function acceptCookies() {
        saveConsent();
        closeBanner();
    }

    /**
     * Crée et affiche la bannière
     */
    function createBanner() {
        // Vérifier si la bannière n'existe pas déjà
        if (document.getElementById('cookieBanner')) {
            return;
        }

        const banner = document.createElement('div');
        banner.id = 'cookieBanner';
        banner.className = 'cookie-banner';

        banner.innerHTML = `
            <div class="cookie-banner-content">
                <div class="cookie-banner-text">
                    <h3>Cookies et confidentialité</h3>
                    <p>
                        Ce site utilise uniquement des <strong>cookies strictement nécessaires</strong>
                        (session d'authentification et préférences de thème).
                        Aucun cookie de tracking ou analytique n'est utilisé.
                        <a href="/privacy-policy">En savoir plus</a>
                    </p>
                </div>
                <div class="cookie-banner-actions">
                    <button class="btn btn-secondary" onclick="window.cookieBanner.moreInfo()">
                        En savoir plus
                    </button>
                    <button class="btn" onclick="window.cookieBanner.accept()">
                        J'ai compris
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(banner);

        // Afficher la bannière avec animation après un court délai
        setTimeout(() => {
            banner.classList.add('show');
        }, 100);
    }

    /**
     * Rouvre la bannière (appelé depuis le footer)
     */
    function reopenBanner() {
        // Retirer le consentement pour forcer le réaffichage
        localStorage.removeItem(COOKIE_CONSENT_KEY);
        localStorage.removeItem(COOKIE_BANNER_DISMISSED_KEY);

        // Créer et afficher la bannière
        createBanner();
    }

    /**
     * Redirige vers la politique de confidentialité
     */
    function moreInfo() {
        window.location.href = '/privacy-policy';
    }

    /**
     * Initialisation au chargement de la page
     */
    function init() {
        // Afficher la bannière si l'utilisateur n'a pas encore consenti
        if (!hasConsent()) {
            createBanner();
        }
    }

    // Exposer les fonctions publiques
    window.cookieBanner = {
        accept: acceptCookies,
        reopen: reopenBanner,
        moreInfo: moreInfo
    };

    // Fonction globale pour la compatibilité avec le footer existant
    window.reopenCookieBanner = reopenBanner;

    // Initialiser au chargement du DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
