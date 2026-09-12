// static/app.js
'use strict';

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    setupToastContainer();
    setupGradeCalculations();
    setupForms();
}

// --- UI Utilities ---

function setupToastContainer() {
    if (!document.getElementById('toast-container')) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
        document.body.appendChild(container);
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    const baseClasses = 'px-4 py-3 rounded shadow-lg text-white font-medium transition-all duration-300 transform translate-y-0 opacity-100 flex items-center justify-between min-w-[250px]';
    const typeClasses = type === 'success' ? 'bg-green-600' : type === 'error' ? 'bg-red-600' : 'bg-blue-600';
    
    toast.className = `${baseClasses} ${typeClasses}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button class="ml-4 text-white hover:text-gray-200 focus:outline-none" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function toggleButtonState(button, isLoading, loadingText = 'Traitement...') {
    if (!button) return;
    if (isLoading) {
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>${loadingText}`;
        button.disabled = true;
        button.classList.add('opacity-75', 'cursor-not-allowed');
    } else {
        button.innerHTML = button.dataset.originalText || 'Soumettre';
        button.disabled = false;
        button.classList.remove('opacity-75', 'cursor-not-allowed');
    }
}

// --- API Utilities ---

async function apiCall(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };

    const options = {
        method,
        headers
    };

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(endpoint, options);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Une erreur est survenue lors de la requête.');
        }

        return data;
    } catch (error) {
        console.error(`API Error [${method} ${endpoint}]:`, error);
        throw error;
    }
}

// --- Core Features ---

function setupGradeCalculations() {
    const gradeInputs = document.querySelectorAll('.grade-input');
    if (gradeInputs.length === 0) return;

    gradeInputs.forEach(input => {
        input.addEventListener('input', (e) => {
            validateGradeInput(e.target);
            calculateRowAverages(e.target.closest('tr'));
            calculateGlobalAverage(e.target.closest('table'));
        });
    });
}

function validateGradeInput(input) {
    let value = parseFloat(input.value);
    if (isNaN(value)) return;
    
    if (value < 0) input.value = 0;
    if (value > 20) input.value = 20;
}

function calculateRowAverages(row) {
    if (!row) return;

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

    const averageCell = row.querySelector('.row-average');
    if (averageCell) {
        const average = count > 0 ? (total / count) : 0;
        averageCell.textContent = average.toFixed(2);
        
        if (average >= 10) {
            averageCell.classList.remove('text-red-600');
            averageCell.classList.add('text-green-600');
        } else {
            averageCell.classList.remove('text-green-600');
            averageCell.classList.add('text-red-600');
        }
    }
}

function calculateGlobalAverage(table) {
    if (!table) return;

    const averageCells = table.querySelectorAll('.row-average');
    let totalAverage = 0;
    let count = 0;

    averageCells.forEach(cell => {
        const val = parseFloat(cell.textContent);
        if (!isNaN(val) && val > 0) {
            totalAverage += val;
            count++;
        }
    });

    const globalAverageCell = document.getElementById('global-average');
    if (globalAverageCell) {
        const globalAverage = count > 0 ? (totalAverage / count) : 0;
        globalAverageCell.textContent = globalAverage.toFixed(2);
    }
}

function setupForms() {
    const gradeForm = document.getElementById('form-saisie-notes');
    if (gradeForm) {
        gradeForm.addEventListener('submit', handleGradeSubmission);
    }

    const paymentForm = document.getElementById('form-paiement-momo');
    if (paymentForm) {
        paymentForm.addEventListener('submit', handlePaymentSubmission);
    }

    const parentPortalForm = document.getElementById('form-portail-parent');
    if (parentPortalForm) {
        parentPortalForm.addEventListener('submit', handleParentSearch);
    }
}

async function handleGradeSubmission(event) {
    event.preventDefault();
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const ecoleId = form.dataset.ecoleId;
    const classeId = form.dataset.classeId;
    const matiereId = form.dataset.matiereId;
    
    const gradesData = [];
    const rows = form.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        const eleveId = row.dataset.eleveId;
        const inputs = row.querySelectorAll('.grade-input');
        const eleveGrades = { eleve_id: eleveId, notes: {} };
        
        inputs.forEach(input => {
            const seq = input.dataset.sequence;
            const val = parseFloat(input.value);
            if (!isNaN(val)) {
                eleveGrades.notes[`seq_${seq}`] = val;
            }
        });
        
        if (Object.keys(eleveGrades.notes).length > 0) {
            gradesData.push(eleveGrades);
        }
    });

    if (gradesData.length === 0) {
        showToast('Veuillez saisir au moins une note avant de soumettre.', 'error');
        return;
    }

    const payload = {
        ecole_id: ecoleId,
        classe_id: classeId,
        matiere_id: matiereId,
        donnees: gradesData
    };

    try {
        toggleButtonState(submitBtn, true, 'Enregistrement...');
        const response = await apiCall('/api/grades', 'POST', payload);
        showToast(response.message || 'Notes enregistrées avec succès !', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        toggleButtonState(submitBtn, false);
    }
}

async function handlePaymentSubmission(event) {
    event.preventDefault();
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const formData = new FormData(form);
    const payload = {
        ecole_id: formData.get('ecole_id'),
        telephone: formData.get('telephone'),
        montant: parseFloat(formData.get('montant')),
        operateur: formData.get('operateur'),
        motif: formData.get('motif') || 'Paiement frais scolaires'
    };

    if (!payload.telephone || payload.telephone.length < 9) {
        showToast('Numéro de téléphone invalide.', 'error');
        return;
    }

    if (isNaN(payload.montant) || payload.montant <= 0) {
        showToast('Le montant doit être supérieur à 0 FCFA.', 'error');
        return;
    }

    try {
        toggleButtonState(submitBtn, true, 'Initiation du paiement...');
        const response = await apiCall('/api/pay', 'POST', payload);
        
        showToast('Veuillez valider le paiement sur votre téléphone (Code PIN).', 'success');
        
        if (response.transaction_id) {
            pollPaymentStatus(response.transaction_id, submitBtn);
        } else {
            toggleButtonState(submitBtn, false);
            form.reset();
        }
    } catch (error) {
        showToast(error.message, 'error');
        toggleButtonState(submitBtn, false);
    }
}

async function pollPaymentStatus(transactionId, submitBtn) {
    let attempts = 0;
    const maxAttempts = 12; 
    const interval = 5000; 

    const checkStatus = async () => {
        try {
            const response = await apiCall(`/api/pay/status/${transactionId}`, 'GET');
            
            if (response.status === 'SUCCESS') {
                showToast('Paiement confirmé avec succès !', 'success');
                toggleButtonState(submitBtn, false);
                document.getElementById('form-paiement-momo').reset();
                return;
            } else if (response.status === 'FAILED') {
                showToast('Le paiement a échoué ou a été annulé.', 'error');
                toggleButtonState(submitBtn, false);
                return;
            }

            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(checkStatus, interval);
            } else {
                showToast('Délai d\'attente dépassé. Veuillez vérifier votre solde.', 'error');
                toggleButtonState(submitBtn, false);
            }
        } catch (error) {
            console.error('Erreur lors de la vérification du statut:', error);
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(checkStatus, interval);
            } else {
                toggleButtonState(submitBtn, false);
            }
        }
    };

    setTimeout(checkStatus, interval);
}

async function handleParentSearch(event) {
    event.preventDefault();
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const matricule = form.querySelector('input[name="matricule"]').value.trim();
    const codeAcces = form.querySelector('input[name="code_acces"]').value.trim();
    const resultsContainer = document.getElementById('resultats-bulletin');

    if (!matricule || !codeAcces) {
        showToast('Veuillez fournir le matricule et le code d\'accès.', 'error');
        return;
    }

    try {
        toggleButtonState(submitBtn, true, 'Recherche...');
        const response = await apiCall(`/api/report?matricule=${encodeURIComponent(matricule)}&code=${encodeURIComponent(codeAcces)}`, 'GET');
        
        renderReportCard(response.data, resultsContainer);
        showToast('Bulletin récupéré avec succès.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
        if (resultsContainer) {
            resultsContainer.innerHTML = `<div class="p-4 bg-red-50 text-red-700 rounded border border-red-200">Aucun bulletin trouvé pour ces identifiants.</div>`;
        }
    } finally {
        toggleButtonState(submitBtn, false);
    }
}

function renderReportCard(data, container) {
    if (!container || !data) return;

    const { eleve, ecole, classe, sequences, moyenne_generale, rang, appreciation } = data;

    let html = `
        <div class="bg-white shadow rounded-lg p-6 mt-6 border border-gray-200">
            <div class="text-center border-b pb-4 mb-4">
                <h2 class="text-2xl font-bold text-gray-800">${ecole.nom}</h2>
                <p class="text-gray-600">Bulletin de notes - Année Scolaire en cours</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                    <p><span class="font-semibold text-gray-700">Élève :</span> ${eleve.nom} ${eleve.prenom}</p>
                    <p><span class="font-semibold text-gray-700">Matricule :</span> ${eleve.matricule}</p>
                </div>
                <div>
                    <p><span class="font-semibold text-gray-700">Classe :</span> ${classe.nom}</p>
                    <p><span class="font-semibold text-gray-700">Effectif :</span> ${classe.effectif}</p>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 mb-6">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Matière</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 1</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 2</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 3</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 4</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 5</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Seq 6</th>
                            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Moyenne</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
    `;

    data.matieres.forEach(matiere => {
        html += `<tr>
            <td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">${matiere.nom}</td>`;
        
        let totalMatiere = 0;
        let countMatiere = 0;

        for (let i = 1; i <= 6; i++) {
            const note = matiere.notes[`seq_${i}`];
            const displayNote = note !== undefined && note !== null ? note.toFixed(2) : '-';
            if (note !== undefined && note !== null) {
                totalMatiere += note;
                countMatiere++;
            }
            html += `<td class="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-500">${displayNote}</td>`;
        }

        const moyenneMatiere = countMatiere > 0 ? (totalMatiere / countMatiere).toFixed(2) : '-';
        const colorClass = moyenneMatiere >= 10 ? 'text-green-600 font-bold' : 'text-red-600 font-bold';

        html += `<td class="px-4 py-3 whitespace-nowrap text-sm text-center ${moyenneMatiere !== '-' ? colorClass : 'text-gray-500'}">${moyenneMatiere}</td>
        </tr>`;
    });

    html += `
                    </tbody>
                </table>
            </div>

            <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 flex flex-col md:flex-row justify-between items-center">
                <div class="mb-2 md:mb-0">
                    <span class="text-lg font-semibold text-gray-700">Moyenne Générale : </span>
                    <span class="text-2xl font-bold ${moyenne_generale >= 10 ? 'text-green-600' : 'text-red-600'}">${moyenne_generale.toFixed(2)} / 20</span>
                </div>
                <div class="mb-2 md:mb-0">
                    <span class="text-lg font-semibold text-gray-700">Rang : </span>
                    <span class="text-xl font-bold text-blue-600">${rang}${rang === 1 ? 'er' : 'ème'}</span>
                </div>
                <div>
                    <span class="text-lg font-semibold text-gray-700">Appréciation : </span>
                    <span class="text-lg font-medium text-gray-800">${appreciation}</span>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
}