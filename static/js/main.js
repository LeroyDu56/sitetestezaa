/**
 * Main JavaScript file for Novania website
 */

document.addEventListener('DOMContentLoaded', function() {
    // Débogage pour confirmer le chargement du DOM
    console.log('DOM chargé - Script initialisé');

    // Effet de défilement pour le header
    window.addEventListener('scroll', function() {
        const header = document.querySelector('header');
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
    
    // Mobile menu toggle
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const navbar = document.querySelector('.navbar');
    
    if (mobileMenuToggle) {
        console.log('Bouton hamburger trouvé');
        
        // Solution directe et simple pour la gestion du clic
        mobileMenuToggle.onclick = function() {
            console.log('Clic sur hamburger détecté');
            navbar.classList.toggle('mobile-open');
            console.log('État de la classe mobile-open:', navbar.classList.contains('mobile-open'));
        };
    } else {
        console.error('Bouton hamburger non trouvé!');
    }
    
    // Close mobile menu when clicking on links
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            navbar.classList.remove('mobile-open');
        });
    });
    
    // User dropdown menu toggle
    const userDropdownToggle = document.getElementById('user-dropdown-toggle');
    const userDropdownMenu = document.getElementById('user-dropdown-menu');
    
    if (userDropdownToggle && userDropdownMenu) {
        // Toggle dropdown when clicking on avatar
        userDropdownToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdownMenu.classList.toggle('active');
        });
        
        // Close dropdown when clicking elsewhere
        document.addEventListener('click', function() {
            if (userDropdownMenu.classList.contains('active')) {
                userDropdownMenu.classList.remove('active');
            }
        });
        
        // Prevent dropdown from closing when clicking inside it
        userDropdownMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // Handle message notifications
    const messageCloseButtons = document.querySelectorAll('.message-close');
    if (messageCloseButtons.length > 0) {
        messageCloseButtons.forEach(button => {
            button.addEventListener('click', function() {
                const message = this.parentElement;
                message.style.opacity = '0';
                setTimeout(() => {
                    message.remove();
                }, 300);
            });
        });
        
        // Auto-hide messages after 5 seconds
        setTimeout(() => {
            document.querySelectorAll('.message').forEach(message => {
                message.style.opacity = '0';
                setTimeout(() => {
                    message.remove();
                }, 300);
            });
        }, 5000);
    }
    

    // Copy server IP functionality
    const copyIpButton = document.getElementById('copy-ip');
    const serverIpElement = document.getElementById('server-ip');
    
    if (serverIpElement) {
        serverIpElement.addEventListener('click', function(e) {
            const serverIP = 'play.novania.fr';
            navigator.clipboard.writeText(serverIP).then(function() {
                // Créer un élément de notification
                const notification = document.createElement('div');
                notification.className = 'copy-notification';
                notification.innerHTML = '<i class="fas fa-check"></i> Copied!';
                
                // Positionner la notification
                const rect = serverIpElement.getBoundingClientRect();
                notification.style.top = `${rect.top - 40}px`;
                notification.style.left = `${rect.left + rect.width / 2}px`;
                
                document.body.appendChild(notification);
                
                // Animer l'élément IP
                serverIpElement.classList.add('copied');
                
                // Supprimer la notification après l'animation
                setTimeout(() => {
                    notification.classList.add('fade-out');
                    setTimeout(() => {
                        document.body.removeChild(notification);
                    }, 300);
                }, 1500);
                
                // Réinitialiser l'état de l'élément IP
                setTimeout(() => {
                    serverIpElement.classList.remove('copied');
                }, 2000);
            });
        });
        
        // Effet de surbrillance au hover
        serverIpElement.addEventListener('mouseenter', function() {
            this.classList.add('hover');
        });
        
        serverIpElement.addEventListener('mouseleave', function() {
            this.classList.remove('hover');
        });
    }
    
    // Permettre de copier l'IP en cliquant directement sur l'élément qui l'affiche
    if (serverIpElement) {
        serverIpElement.addEventListener('click', function() {
            const serverIP = 'play.novania.fr';
            navigator.clipboard.writeText(serverIP).then(function() {
                serverIpElement.classList.add('copied');
                
                setTimeout(function() {
                    serverIpElement.classList.remove('copied');
                }, 2000);
            });
        });
    }
    
    // FAQ Toggle functionality
    const faqQuestions = document.querySelectorAll('.faq-question');
    if (faqQuestions.length > 0) {
        faqQuestions.forEach(question => {
            question.addEventListener('click', function() {
                const answer = this.nextElementSibling;
                
                // Toggle display
                if (answer.style.display === 'block') {
                    answer.style.display = 'none';
                    this.querySelector('i').classList.replace('fa-chevron-up', 'fa-chevron-down');
                } else {
                    answer.style.display = 'block';
                    this.querySelector('i').classList.replace('fa-chevron-down', 'fa-chevron-up');
                }
            });
        });
        
        // Initially hide all answers
        document.querySelectorAll('.faq-answer').forEach(answer => {
            answer.style.display = 'none';
        });
    }
    
    // Add active class to current page in navigation
    const currentLocation = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-links a');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (currentLocation === href || (href !== '/' && currentLocation.includes(href))) {
            item.classList.add('active');
        }
    });
    
    // Animation de nombre de joueurs (effet de compteur)
    const playerCount = document.querySelector('.player-count');
    if (playerCount) {
        const text = playerCount.textContent;
        const numbers = text.match(/\d+/g);
        
        if (numbers && numbers.length === 2) {
            const currentPlayers = parseInt(numbers[0]);
            const maxPlayers = parseInt(numbers[1]);
            
            // Animation du compteur
            let count = 0;
            const duration = 1500; // ms
            const interval = 30; // ms
            const increment = Math.ceil(currentPlayers / (duration / interval));
            
            const counter = setInterval(() => {
                count += increment;
                if (count >= currentPlayers) {
                    count = currentPlayers;
                    clearInterval(counter);
                }
                playerCount.textContent = `${count}/${maxPlayers}`;
            }, interval);
        }
    }
    
    // Effet de surbrillance aléatoire pour server-ip
    if (serverIpElement) {
        function randomHighlight() {
            const duration = Math.random() * 1000 + 2000; // Entre 2 et 3 secondes
            serverIpElement.style.boxShadow = 'inset 0 2px 5px rgba(0, 0, 0, 0.3), 0 0 15px rgba(255, 215, 0, 0.6)';
            
            setTimeout(() => {
                serverIpElement.style.boxShadow = 'inset 0 2px 5px rgba(0, 0, 0, 0.3)';
                
                // Planifier la prochaine surbrillance après un délai aléatoire
                setTimeout(randomHighlight, Math.random() * 4000 + 3000);
            }, duration);
        }
        
        // Démarrer l'effet après un délai initial
        setTimeout(randomHighlight, 2000);
    }
    
    // Effet particules pour la section join (version simple)
    const joinSection = document.querySelector('.join-section');
    if (joinSection) {
        // Créer un conteneur pour les particules
        const particlesContainer = document.createElement('div');
        particlesContainer.className = 'particles-container';
        particlesContainer.style.position = 'absolute';
        particlesContainer.style.top = '0';
        particlesContainer.style.left = '0';
        particlesContainer.style.width = '100%';
        particlesContainer.style.height = '100%';
        particlesContainer.style.overflow = 'hidden';
        particlesContainer.style.zIndex = '0';
        joinSection.prepend(particlesContainer);
        
        // Créer quelques particules
        const particleCount = window.innerWidth < 768 ? 15 : 30;
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.position = 'absolute';
            particle.style.width = `${Math.random() * 4 + 2}px`;
            particle.style.height = particle.style.width;
            particle.style.backgroundColor = 'rgba(255, 215, 0, 0.7)';
            particle.style.borderRadius = '50%';
            particle.style.top = `${Math.random() * 100}%`;
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.boxShadow = '0 0 10px rgba(255, 215, 0, 0.7)';
            particle.style.opacity = Math.random() * 0.5 + 0.3;
            particle.style.zIndex = '0';
            
            // Animation de déplacement
            const duration = Math.random() * 60 + 30;
            particle.style.animation = `float ${duration}s infinite linear`;
            
            // Ajouter une règle d'animation unique
            const keyframes = `
                @keyframes float {
                    0% {
                        transform: translate(0, 0);
                    }
                    25% {
                        transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px);
                    }
                    50% {
                        transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px);
                    }
                    75% {
                        transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px);
                    }
                    100% {
                        transform: translate(0, 0);
                    }
                }
            `;
            
            // Ajouter les keyframes au document
            const style = document.createElement('style');
            style.innerHTML = keyframes;
            document.head.appendChild(style);
            
            // Ajouter la particule au conteneur
            particlesContainer.appendChild(particle);
        }
    }
    
    // Effet de highlight pour le status online
    const statusIndicator = document.querySelector('.status-indicator.status-online');
    if (statusIndicator) {
        function pulseEffect() {
            statusIndicator.style.boxShadow = '0 0 15px #2ecc71';
            
            setTimeout(() => {
                statusIndicator.style.boxShadow = '0 0 5px #2ecc71';
                
                setTimeout(pulseEffect, 2000);
            }, 1000);
        }
        
        pulseEffect();
    }
});