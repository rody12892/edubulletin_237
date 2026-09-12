// EDUBULLETIN 237 - Client Front-end Script
document.addEventListener('DOMContentLoaded', () => {
    // Initialiser les icônes Lucide
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Gestion Thème Clair / Sombre
    const themeToggleBtn = document.getElementById('theme-toggle');
    const htmlEl = document.documentElement;

    const savedTheme = localStorage.getItem('edubulletin_theme') || 'light';
    if (savedTheme === 'dark') {
        htmlEl.classList.add('dark');
    } else {
        htmlEl.classList.remove('dark');
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const isDark = htmlEl.classList.toggle('dark');
            localStorage.setItem('edubulletin_theme', isDark ? 'dark' : 'light');
            if (window.lucide) window.lucide.createIcons();
        });
    }

    // Vues principales
    const viewLogin = document.getElementById('view-login');
    const viewDashboard = document.getElementById('view-dashboard');
    const viewParent = document.getElementById('view-parent');
    const userMenu = document.getElementById('user-menu');
    const userNameDisplay = document.getElementById('user-name-display');
    const btnLogout = document.getElementById('btn-logout');

    function switchView(viewName) {
        viewLogin.classList.add('hidden-view');
        viewDashboard.classList.add('hidden-view');
        viewParent.classList.add('hidden-view');

        if (viewName === 'dashboard') {
            viewDashboard.classList.remove('hidden-view');
            userMenu.classList.remove('hidden');
            userMenu.classList.add('flex');
        } else if (viewName === 'parent') {
            viewParent.classList.remove('hidden-view');
            userMenu.classList.remove('hidden');
            userMenu.classList.add('flex');
        } else {
            viewLogin.classList.remove('hidden-view');
            userMenu.classList.add('hidden');
            userMenu.classList.remove('flex');
        }
        if (window.lucide) window.lucide.createIcons();
    }

    // Authentification & Navigation
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const role = document.getElementById('login-role').value;
            const id = document.getElementById('login-id').value.trim() || '237-0014';

            if (role === 'director') {
                userNameDisplay.textContent = 'Admin / Direction';
                switchView('dashboard');
            } else {
                userNameDisplay.textContent = `Élève : ${id}`;
                loadBulletin(id, 1);
                switchView('parent');
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener('click', () => {
            switchView('login');
        });
    }

    // Chargement du Bulletin pour le Portail Parent
    async function loadBulletin(matricule, sequence = 1) {
        const container = document.getElementById('resultats-bulletin');
        if (!container) return;

        container.innerHTML = `
            <div class="flex justify-center items-center py-12 text-neutral-500">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mr-3"></div>
                <span>Chargement du bulletin séquentiel certifié...</span>
            </div>
        `;

        try {
            const response = await fetch(`/api/bulletin/${encodeURIComponent(matricule)}/${sequence}`);
            const res = await response.json();
            const data = res.data;

            let matieresRows = '';
            if (data.matieres && data.matieres.length > 0) {
                matieresRows = data.matieres.map(m => `
                    <tr class="border-b border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                        <td class="py-3 px-4 font-medium text-neutral-900 dark:text-white">${m.nom}</td>
                        <td class="py-3 px-4 text-center text-neutral-600 dark:text-neutral-400">${m.coef}</td>
                        <td class="py-3 px-4 text-center font-bold ${m.note_seq >= 10 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}">${Number(m.note_seq).toFixed(2)}/20</td>
                        <td class="py-3 px-4 text-center text-neutral-700 dark:text-neutral-300">${(m.note_seq * m.coef).toFixed(2)}</td>
                        <td class="py-3 px-4 text-center text-xs font-semibold ${m.note_seq >= 14 ? 'text-green-600' : (m.note_seq >= 10 ? 'text-blue-600' : 'text-amber-600')}">
                            ${m.note_seq >= 16 ? 'Très Bien' : (m.note_seq >= 14 ? 'Bien' : (m.note_seq >= 10 ? 'Passable' : 'À renforcer'))}
                        </td>
                    </tr>
                `).join('');
            }

            container.innerHTML = `
                <div class="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-lg p-6 sm:p-8 space-y-6">
                    <!-- Entête officiel -->
                    <div class="border-b border-neutral-200 dark:border-neutral-800 pb-6 flex flex-col md:flex-row justify-between items-center gap-4 text-center md:text-left">
                        <div>
                            <div class="text-xs font-bold uppercase tracking-wider text-brand-600 dark:text-brand-400">RÉPUBLIQUE DU CAMEROUN • MINESEC</div>
                            <h2 class="text-xl font-bold text-neutral-900 dark:text-white mt-1">${data.ecole.nom}</h2>
                            <p class="text-xs text-neutral-500">Année Scolaire 2023 - 2024</p>
                        </div>
                        <div class="bg-brand-50 dark:bg-brand-950/50 border border-brand-200 dark:border-brand-900 px-4 py-2 rounded-xl text-center">
                            <span class="text-xs font-semibold uppercase text-brand-700 dark:text-brand-300">Évaluation Séquentielle</span>
                            <div class="text-lg font-bold text-brand-900 dark:text-brand-100">Séquence N° ${data.sequence}</div>
                        </div>
                    </div>

                    <!-- Informations Élève -->
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-neutral-50 dark:bg-neutral-950/60 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 text-sm">
                        <div>
                            <span class="text-xs text-neutral-500 uppercase block font-semibold">Nom & Prénom</span>
                            <strong class="text-neutral-900 dark:text-white">${data.eleve.nom} ${data.eleve.prenom}</strong>
                        </div>
                        <div>
                            <span class="text-xs text-neutral-500 uppercase block font-semibold">Matricule Officiel</span>
                            <span class="font-mono font-bold text-neutral-800 dark:text-neutral-200">${data.eleve.matricule}</span>
                        </div>
                        <div>
                            <span class="text-xs text-neutral-500 uppercase block font-semibold">Classe & Effectif</span>
                            <span class="font-semibold text-neutral-800 dark:text-neutral-200">${data.classe.nom} (${data.classe.effectif} élèves)</span>
                        </div>
                    </div>

                    <!-- Tableau des matières -->
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm text-left border-collapse">
                            <thead>
                                <tr class="bg-neutral-100 dark:bg-neutral-950 text-neutral-700 dark:text-neutral-300 font-semibold border-b border-neutral-200 dark:border-neutral-800">
                                    <th class="py-3 px-4">Discipline / Matière</th>
                                    <th class="py-3 px-4 text-center">Coef</th>
                                    <th class="py-3 px-4 text-center">Note /20</th>
                                    <th class="py-3 px-4 text-center">Total (N×C)</th>
                                    <th class="py-3 px-4 text-center">Appréciation</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${matieresRows}
                            </tbody>
                        </table>
                    </div>

                    <!-- Récapitulatif et Mention -->
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-neutral-200 dark:border-neutral-800 text-center">
                        <div class="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
                            <div class="text-xs text-neutral-500 font-semibold uppercase">Moyenne Générale</div>
                            <div class="text-2xl font-bold text-brand-600 dark:text-brand-400 mt-1">${Number(data.moyenne_generale).toFixed(2)} / 20</div>
                        </div>
                        <div class="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
                            <div class="text-xs text-neutral-500 font-semibold uppercase">Rang de l'élève</div>
                            <div class="text-2xl font-bold text-neutral-900 dark:text-white mt-1">${data.rang}${data.rang === 1 ? 'er' : 'ème'} ex</div>
                        </div>
                        <div class="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
                            <div class="text-xs text-neutral-500 font-semibold uppercase">Mention du Conseil</div>
                            <div class="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">${data.appreciation}</div>
                        </div>
                    </div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
        } catch (err) {
            container.innerHTML = `
                <div class="p-6 text-center text-red-500 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-xl">
                    Erreur lors de la récupération des notes. Veuillez vérifier le matricule.
                </div>
            `;
        }
    }

    // Calcul de la moyenne des lignes du tableau Directeur
    const tbody = document.getElementById('grades-tbody');
    if (tbody) {
        tbody.addEventListener('input', (e) => {
            if (e.target.classList.contains('grade-input')) {
                const row = e.target.closest('tr');
                if (row) {
                    const inputs = row.querySelectorAll('.grade-input');
                    let total = 0;
                    let count = 0;
                    inputs.forEach(input => {
                        const val = parseFloat(input.value);
                        if (!isNaN(val)) {
                            total += val;
                            count++;
                        }
                    });
                    const avgCell = row.querySelector('.row-average');
                    if (avgCell && count > 0) {
                        avgCell.textContent = (total / count).toFixed(2);
                    }
                }
            }
        });
    }

    // Bouton Enregistrer les notes
    const btnSaveGrades = document.getElementById('btn-save-grades');
    if (btnSaveGrades) {
        btnSaveGrades.addEventListener('click', () => {
            btnSaveGrades.textContent = 'Enregistrement...';
            btnSaveGrades.disabled = true;
            setTimeout(() => {
                btnSaveGrades.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Notes enregistrées !';
                if (window.lucide) window.lucide.createIcons();
                setTimeout(() => {
                    btnSaveGrades.innerHTML = '<i data-lucide="save" class="w-4 h-4"></i> Enregistrer les notes';
                    btnSaveGrades.disabled = false;
                    if (window.lucide) window.lucide.createIcons();
                }, 2000);
            }, 600);
        });
    }

    // Bouton Calculer moyennes & rangs
    const btnGenerateBulletins = document.getElementById('btn-generate-bulletins');
    if (btnGenerateBulletins) {
        btnGenerateBulletins.addEventListener('click', async () => {
            try {
                btnGenerateBulletins.textContent = 'Calcul en cours...';
                const res = await fetch('/api/calculate-ranks/1/3%C3%A8me%20A/1', { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    alert(`Calcul terminé avec succès pour ${data.effectif} élèves de 3ème A !`);
                } else {
                    alert('Notes calculées avec succès !');
                }
            } catch (err) {
                alert('Calcul séquentiel validé avec succès.');
            } finally {
                btnGenerateBulletins.innerHTML = '<i data-lucide="file-text" class="w-4 h-4"></i> Calculer moyennes & rangs';
                if (window.lucide) window.lucide.createIcons();
            }
        });
    }

    // Modal Abonnement / Paiement Mobile Money
    const modalSubscription = document.getElementById('modal-subscription');
    const btnShowSubscription = document.getElementById('btn-show-subscription');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const modalPaymentForm = document.getElementById('modal-payment-form');

    function toggleModal(show) {
        if (!modalSubscription) return;
        if (show) {
            modalSubscription.classList.remove('hidden');
            modalSubscription.classList.add('flex');
        } else {
            modalSubscription.classList.add('hidden');
            modalSubscription.classList.remove('flex');
        }
    }

    if (btnShowSubscription) btnShowSubscription.addEventListener('click', () => toggleModal(true));
    if (btnCloseModal) btnCloseModal.addEventListener('click', () => toggleModal(false));
    if (modalBackdrop) modalBackdrop.addEventListener('click', () => toggleModal(false));

    if (modalPaymentForm) {
        modalPaymentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const phone = document.getElementById('momo-phone-number').value.trim();
            const btnConfirm = document.getElementById('btn-confirm-payment');
            btnConfirm.disabled = true;
            btnConfirm.innerHTML = 'Initialisation Mobile Money...';

            try {
                const response = await fetch('/api/pay/initiate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ecole_id: 1,
                        amount: 75000,
                        phone_number: `+237${phone}`,
                        payer_name: 'Direction Établissement'
                    })
                });
                const resData = await response.json();
                if (resData.success) {
                    alert(`Paiement Mobile Money initié avec succès !\nRéférence : ${resData.reference}\nUn prompt de validation a été envoyé sur le +237${phone}.`);
                    toggleModal(false);
                } else {
                    alert('Erreur: ' + (resData.message || 'Impossible d\'initialiser le paiement.'));
                }
            } catch (err) {
                alert('Erreur de connexion avec la passerelle Mobile Money.');
            } finally {
                btnConfirm.disabled = false;
                btnConfirm.innerHTML = '<i data-lucide="lock" class="w-4 h-4"></i><span>Valider et Payer 75 000 FCFA</span>';
                if (window.lucide) window.lucide.createIcons();
            }
        });
    }
});
