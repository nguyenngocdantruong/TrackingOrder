// i18n.js - Internationalization handler
(function() {
    'use strict';

    // Get language from localStorage or default to 'en'
    let currentLanguage = localStorage.getItem('language') || 'en';
    
    // Set language on page load
    if (!localStorage.getItem('language')) {
        localStorage.setItem('language', 'en');
    }

    // Function to change language
    window.changeLanguage = function(lang) {
        if (translations[lang]) {
            currentLanguage = lang;
            localStorage.setItem('language', lang);
            applyTranslations();
            updateLanguageUI();
        }
    };

    // Function to apply translations to all elements with data-i18n attribute
    function applyTranslations() {
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = translations[currentLanguage][key];
            
            if (translation) {
                // Check if element has data-i18n-attr to translate attribute instead of text
                const attr = element.getAttribute('data-i18n-attr');
                if (attr) {
                    element.setAttribute(attr, translation);
                } else {
                    // For elements that might have HTML content, use innerHTML
                    if (element.children.length === 0) {
                        element.textContent = translation;
                    } else {
                        // If has children, only update text nodes
                        const walker = document.createTreeWalker(
                            element,
                            NodeFilter.SHOW_TEXT,
                            null,
                            false
                        );
                        let node;
                        const textNodes = [];
                        while(node = walker.nextNode()) {
                            if (node.nodeValue.trim()) {
                                textNodes.push(node);
                            }
                        }
                        if (textNodes.length === 1) {
                            textNodes[0].nodeValue = translation;
                        }
                    }
                }
            }
        });

        // Update HTML lang attribute
        document.documentElement.lang = currentLanguage;
    }

    // Function to update language switcher UI
    function updateLanguageUI() {
        const langButtons = document.querySelectorAll('.lang-btn');
        langButtons.forEach(btn => {
            const btnLang = btn.getAttribute('data-lang');
            if (btnLang === currentLanguage) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        currentLanguage = localStorage.getItem('language') || 'en';
        applyTranslations();
        updateLanguageUI();
    });

    // Export for debugging
    window.getCurrentLanguage = function() {
        return currentLanguage;
    };
})();
