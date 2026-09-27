// Point d'entrée JS de La Ruche.
//
// Alpine est chargé en build CSP : les composants doivent être déclarés ici
// via Alpine.data() puis référencés par nom dans les gabarits (x-data="nom"),
// jamais sous forme d'expressions JS inline complexes.
document.addEventListener('alpine:init', () => {
  // Écran partagé : recharge la page au changement de période (matin → midi…).
  // Un seul rechargement programmé, pas de sondage régulier : la base Neon
  // peut s'endormir entre deux périodes (quota de calcul).
  Alpine.data('periodClock', () => ({
    init() {
      const seconds = Number(this.$el.dataset.reloadIn);
      if (seconds > 0) {
        // Petite marge pour tomber après la borne côté serveur.
        setTimeout(() => window.location.reload(), (seconds + 5) * 1000);
      }
    },
  }));
});

// Cases à cocher des tâches : l'état change tout de suite côté client
// (optimiste) et HTMX le confirme. Si le serveur refuse ou ne répond pas,
// on remet la case dans son état précédent.
function revertTaskCheckbox(event) {
  const form = event.detail.elt;
  if (!form || !form.matches('[data-task-form]')) return;
  const checkbox = form.querySelector('input[type="checkbox"]');
  if (checkbox) checkbox.checked = !checkbox.checked;
}
document.addEventListener('htmx:responseError', revertTaskCheckbox);
document.addEventListener('htmx:sendError', revertTaskCheckbox);
